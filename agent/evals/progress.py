"""Eval for `check_progress`: does it read the meeting notes the way it should?

A note between two versions is context, not a list of requirements. It should
make a request that was met or missed visible, and what a note only mentions
must not come back as a gap. No unit test can hold that, because the rule is
only as good as what the model does with it.

    uv run python -m evals.progress --model claude
    uv run python -m evals.progress --model claude --cases notatka-tylko-wspomina

Each case is a directory under ``evals/progress_cases/`` holding
``previous.md``, ``current.md`` and ``case.json``. One judge call per case reads
the report for what it does and does not claim.
"""

from __future__ import annotations

import os

# As in `run.py`: read at import time, required by the service, unused here.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://eval:eval@localhost/eval")
os.environ.setdefault("JWT_SECRET", "eval-" + "x" * 40)
os.environ.setdefault("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
os.environ.setdefault("CHECKPOINTS_ENABLED", "false")

import argparse
import json
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, TypeAdapter

from src.application.graph import build_action_graph
from src.application.structured import invoke_structured
from src.application.tasks import (
    _initial_state,  # pyright: ignore[reportPrivateUsage]
)
from src.domain.action import ActionType
from src.infrastructure.llm_factory import (
    ModelCredentials,
    get_llm,
    use_credentials,
)

CASES_DIR = Path(__file__).parent / "progress_cases"
RESULTS_DIR = Path(__file__).parent / "results"

_PROVIDER_KEYS = {"claude": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}
_LOCAL_JUDGE = "qwen3:30b-a3b"


@dataclass(frozen=True)
class ProgressCase:
    """Two versions, the notes between them, and what the report may claim."""

    id: str
    description: str
    previous: str
    current: str
    context: dict[str, Any]
    must_say: tuple[str, ...]
    must_not_say: tuple[str, ...]


def load_cases(only: list[str] | None = None) -> list[ProgressCase]:
    """Every case, or the ones named, in a stable order."""
    cases: list[ProgressCase] = []
    for directory in sorted(CASES_DIR.iterdir()):
        if not (directory / "case.json").exists():
            continue
        raw = cast(
            dict[str, Any], json.loads((directory / "case.json").read_text("utf-8"))
        )
        cases.append(
            ProgressCase(
                id=str(raw["id"]),
                description=str(raw.get("description", "")),
                previous=(directory / "previous.md").read_text("utf-8"),
                current=(directory / "current.md").read_text("utf-8"),
                context=cast(dict[str, Any], raw["context"]),
                must_say=tuple(cast(list[str], raw.get("must_say", []))),
                must_not_say=tuple(cast(list[str], raw.get("must_not_say", []))),
            )
        )
    if only:
        unknown = set(only) - {c.id for c in cases}
        if unknown:
            raise ValueError(f"Unknown progress cases: {sorted(unknown)}")
        cases = [c for c in cases if c.id in only]
    return cases


def report_text(output: dict[str, Any]) -> str:
    """What the supervisor would read."""
    changes = cast(list[dict[str, str]], output.get("changes") or [])
    parts = [
        str(output.get("summary") or ""),
        *[f"{c.get('area', '')}: {c.get('change', '')}" for c in changes],
        *cast(list[str], output.get("concerns") or []),
        *cast(list[str], output.get("next_steps") or []),
    ]
    return "\n".join(p for p in parts if p)


_JUDGE_PROMPT = """You grade a report an automated assistant drafted for a
supervisor, comparing two versions of a thesis.

You get the REPORT, a list of things it MUST SAY, and a list of things it MUST
NOT SAY. A statement counts if the report says it in any language or wording,
including as a concern or a next step.

Return ONLY a raw JSON object, no markdown, in exactly this shape:
{"must_say": {"1": true}, "must_not_say": {"1": false}}
Number the statements from 1; include every one, true when it is said."""


class JudgeReply(BaseModel):
    must_say: dict[str, bool] = {}
    must_not_say: dict[str, bool] = {}


_REPLY = TypeAdapter(JudgeReply)

Judge = Callable[[ProgressCase, dict[str, Any]], JudgeReply]


def _numbered(items: tuple[str, ...]) -> str:
    return "\n".join(f"{i}. {item}" for i, item in enumerate(items, 1)) or "(none)"


def llm_judge(llm: BaseChatModel) -> Judge:
    """A judge backed by a model."""

    def judge(case: ProgressCase, output: dict[str, Any]) -> JudgeReply:
        message = (
            f"REPORT:\n{report_text(output)}\n\n"
            f"MUST SAY:\n{_numbered(case.must_say)}\n\n"
            f"MUST NOT SAY:\n{_numbered(case.must_not_say)}"
        )
        return invoke_structured(
            llm,
            [
                SystemMessage(content=_JUDGE_PROMPT),  # type: ignore[attr-defined]
                HumanMessage(content=message),
            ],
            _REPLY,
            node="progress_judge",
        )

    return judge


@dataclass
class ProgressResult:
    """One case, one model, one run."""

    case_id: str
    model: str
    seconds: float
    error: str | None
    problems: list[str] = field(default_factory=list[str])
    output: dict[str, Any] | None = None

    @property
    def passed(self) -> bool:
        return self.error is None and not self.problems


def score(
    case: ProgressCase,
    output: dict[str, Any],
    verdict: JudgeReply,
    model: str,
    seconds: float,
) -> ProgressResult:
    """Everything the judge found wrong with one run."""
    problems = [
        f"did not say: {item}"
        for i, item in enumerate(case.must_say, 1)
        if not verdict.must_say.get(str(i), False)
    ]
    problems += [
        f"said: {item}"
        for i, item in enumerate(case.must_not_say, 1)
        if verdict.must_not_say.get(str(i), False)
    ]
    return ProgressResult(
        case_id=case.id,
        model=model,
        seconds=seconds,
        error=None,
        problems=problems,
        output=output,
    )


def run_case(
    case: ProgressCase,
    model: str,
    judge: Judge,
    credentials: ModelCredentials | None = None,
) -> ProgressResult:
    """Run one case through the real graph and score what comes out."""
    state = _initial_state(
        str(uuid.uuid4()),
        ActionType.CHECK_PROGRESS,
        f"eval-{case.id}",
        {**case.context, "previous_text": case.previous, "current_text": case.current},
        model,
        "pl",
    )
    graph = build_action_graph(ActionType.CHECK_PROGRESS)
    started = time.monotonic()
    with use_credentials(credentials):
        final = cast(dict[str, Any], graph.invoke(state))  # pyright: ignore[reportUnknownMemberType]
    seconds = round(time.monotonic() - started, 1)
    output = cast(dict[str, Any] | None, final.get("output"))
    if output is None:
        return ProgressResult(
            case_id=case.id,
            model=model,
            seconds=seconds,
            error=str(final.get("error")),
        )
    return score(case, output, judge(case, output), model, seconds)


def render_markdown(results: list[ProgressResult]) -> str:
    """The run as a table, with what went wrong under it."""
    lines = [
        "| case | passed | s |",
        "|---|---|---|",
        *[
            f"| {r.case_id} | {'yes' if r.passed else 'no'} | {r.seconds} |"
            for r in results
        ],
    ]
    for result in results:
        for problem in [result.error] if result.error else result.problems:
            lines.append(f"- {result.case_id}: {problem}")
    return "\n".join(lines)


def _credentials(name: str, flag: str) -> ModelCredentials | None:
    env = _PROVIDER_KEYS.get(name)
    if env is None:
        return None
    key = os.environ.get(env, "")
    if not key:
        raise SystemExit(f"{flag} {name} needs {env} in the environment")
    return ModelCredentials(provider=name, api_key=key)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Score check_progress.")
    parser.add_argument("--model", required=True, help="Ollama tag, claude or openai")
    parser.add_argument("--judge", help=f"default: the provider, else {_LOCAL_JUDGE}")
    parser.add_argument("--cases", nargs="*", help="case ids (default: all)")
    args = parser.parse_args(argv)

    credentials = _credentials(args.model, "--model")
    judge_name = args.judge or (args.model if credentials else _LOCAL_JUDGE)
    judge_key = _credentials(judge_name, "--judge")
    judge_llm = (
        get_llm(credentials=judge_key) if judge_key is not None else get_llm(judge_name)
    )
    judge = llm_judge(judge_llm)

    results: list[ProgressResult] = []
    for case in load_cases(args.cases):
        print(f"… {case.id} on {args.model}", flush=True)
        results.append(run_case(case, args.model, judge, credentials))

    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = RESULTS_DIR / f"{stamp}-progress-{args.model.replace(':', '_')}.json"
    out.write_text(
        json.dumps(
            {
                "model": args.model,
                "judge": judge_name,
                "passed": sum(1 for r in results if r.passed),
                "cases": [asdict(r) | {"passed": r.passed} for r in results],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print()
    print(render_markdown(results))
    print(f"\nwritten to {out}")


if __name__ == "__main__":
    main()
