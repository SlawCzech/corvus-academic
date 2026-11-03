"""Eval for `review_fragment`: is the feedback gentle, and still of use?

The review's eval (`run.py`) counts findings against planted defects; a
fragment has neither. What matters here is what ADR 0014 asks of this action
and what no unit test can hold: it stays formative, it does not blame work in
progress for being unfinished, and it still says so when a chapter is off.

    uv run python -m evals.fragments --model claude
    uv run python -m evals.fragments --model claude --cases poza-tematem

Each case is a directory under ``evals/fragment_cases/`` holding
``fragment.md`` and ``case.json``. The caps and the absence of grades are
plain checks; one judge call per case does what only a model can: reads the
feedback for tone, and for what it does and does not claim.
"""

from __future__ import annotations

import os

# As in `run.py`: read at import time, required by the service, unused here.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://eval:eval@localhost/eval")
os.environ.setdefault("JWT_SECRET", "eval-" + "x" * 40)
os.environ.setdefault("CHECKPOINTS_ENABLED", "false")

import argparse
import json
import re
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
from src.application.prompts.review_fragment import MAX_ADDITIONS, MAX_CHANGES
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

CASES_DIR = Path(__file__).parent / "fragment_cases"
RESULTS_DIR = Path(__file__).parent / "results"

_PROVIDER_KEYS = {"claude": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}

# A grade in any of the shapes a model reaches for: "4/5", "ocena 3", "8 pkt".
_GRADE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*/\s*\d+\b|\bocen[aeęy]\s*:?\s*\d|\b\d+\s*pkt\b|\bpunkt[óo]w\b",
    re.IGNORECASE,
)
# Not "krytyczn" alone: "krytyczne podejście do źródeł" is praise.
_HARSH = re.compile(
    r"niedopuszczaln|niedostateczn|kompletnie|całkowicie błędn|rażąc"
    r"|krytyczn\w*\s+(?:błąd|błęd|brak|wad|uchybien)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FragmentCase:
    """One fragment and what a good word on it looks like."""

    id: str
    description: str
    text: str
    context: dict[str, Any]
    acceptable_directions: tuple[str, ...]
    must_say: tuple[str, ...]
    must_not_say: tuple[str, ...]


def load_cases(only: list[str] | None = None) -> list[FragmentCase]:
    """Every case, or the ones named, in a stable order."""
    cases: list[FragmentCase] = []
    for directory in sorted(CASES_DIR.iterdir()):
        if not (directory / "case.json").exists():
            continue
        raw = cast(
            dict[str, Any], json.loads((directory / "case.json").read_text("utf-8"))
        )
        cases.append(
            FragmentCase(
                id=str(raw["id"]),
                description=str(raw.get("description", "")),
                text=(directory / "fragment.md").read_text("utf-8"),
                context=cast(dict[str, Any], raw["context"]),
                acceptable_directions=tuple(
                    cast(list[str], raw["acceptable_directions"])
                ),
                must_say=tuple(cast(list[str], raw.get("must_say", []))),
                must_not_say=tuple(cast(list[str], raw.get("must_not_say", []))),
            )
        )
    if only:
        unknown = set(only) - {c.id for c in cases}
        if unknown:
            raise ValueError(f"Unknown fragment cases: {sorted(unknown)}")
        cases = [c for c in cases if c.id in only]
    return cases


def feedback_text(output: dict[str, Any]) -> str:
    """What the student would read: everything but the summary."""
    changes = cast(list[dict[str, str]], output.get("changes") or [])
    parts = [
        str(output.get("answer") or ""),
        *cast(list[str], output.get("strengths") or []),
        *cast(list[str], output.get("addressed") or []),
        *[c.get("point", "") for c in changes],
        *cast(list[str], output.get("additions") or []),
        str(output.get("next_step") or ""),
    ]
    return "\n".join(p for p in parts if p)


def plain_checks(case: FragmentCase, output: dict[str, Any]) -> list[str]:
    """What is wrong that needs no model to see."""
    problems: list[str] = []
    direction = str(output.get("direction"))
    if direction not in case.acceptable_directions:
        problems.append(f"direction {direction}")
    if len(cast(list[Any], output.get("changes") or [])) > MAX_CHANGES:
        problems.append("too many changes")
    if len(cast(list[Any], output.get("additions") or [])) > MAX_ADDITIONS:
        problems.append("too many additions")
    if not output.get("strengths"):
        problems.append("nothing named as working")
    if not str(output.get("summary") or "").strip():
        problems.append("no summary")
    text = feedback_text(output)
    if _GRADE.search(text):
        problems.append("a grade in the feedback")
    if match := _HARSH.search(text):
        problems.append(f"harsh wording: {match.group()}")
    return problems


_JUDGE_PROMPT = """You grade feedback an automated assistant drafted for a
supervisor, about a fragment of a thesis still being written. It must read as
encouragement to continue, not as an assessment.

You get the FEEDBACK, a list of things it MUST SAY, and a list of things it MUST
NOT SAY. A statement counts if the feedback says it in any language or wording.

Return ONLY a raw JSON object, no markdown, in exactly this shape:
{"encouraging": true, "must_say": {"1": true}, "must_not_say": {"1": false}}
`encouraging` is true when a student reading this would want to keep going.
Number the statements from 1; include every one, true when it is said."""


class JudgeReply(BaseModel):
    encouraging: bool
    must_say: dict[str, bool] = {}
    must_not_say: dict[str, bool] = {}


_REPLY = TypeAdapter(JudgeReply)

Judge = Callable[[FragmentCase, dict[str, Any]], JudgeReply]


def _numbered(items: tuple[str, ...]) -> str:
    return "\n".join(f"{i}. {item}" for i, item in enumerate(items, 1)) or "(none)"


def llm_judge(llm: BaseChatModel) -> Judge:
    """A judge backed by a model."""

    def judge(case: FragmentCase, output: dict[str, Any]) -> JudgeReply:
        message = (
            f"FEEDBACK:\n{feedback_text(output)}\n\n"
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
            node="fragment_judge",
        )

    return judge


@dataclass
class FragmentResult:
    """One case, one model, one run."""

    case_id: str
    model: str
    seconds: float
    error: str | None
    direction: str | None
    problems: list[str] = field(default_factory=list[str])
    output: dict[str, Any] | None = None

    @property
    def passed(self) -> bool:
        return self.error is None and not self.problems


def score(
    case: FragmentCase,
    output: dict[str, Any],
    verdict: JudgeReply,
    model: str,
    seconds: float,
) -> FragmentResult:
    """Everything wrong with one run, from the checks and the judge's reading."""
    problems = plain_checks(case, output)
    if not verdict.encouraging:
        problems.append("not encouraging")
    problems += [
        f"did not say: {item}"
        for i, item in enumerate(case.must_say, 1)
        if not verdict.must_say.get(str(i), False)
    ]
    problems += [
        f"said: {item}"
        for i, item in enumerate(case.must_not_say, 1)
        if verdict.must_not_say.get(str(i), False)
    ]
    return FragmentResult(
        case_id=case.id,
        model=model,
        seconds=seconds,
        error=None,
        direction=str(output.get("direction")),
        problems=problems,
        output=output,
    )


def run_case(
    case: FragmentCase,
    model: str,
    judge: Judge,
    credentials: ModelCredentials,
) -> FragmentResult:
    """Run one case through the real graph and score what comes out."""
    action_id = str(uuid.uuid4())
    state = _initial_state(
        action_id,
        ActionType.REVIEW_FRAGMENT,
        f"eval-{case.id}",
        {**case.context, "text": case.text},
        model,
        "pl",
    )
    graph = build_action_graph(ActionType.REVIEW_FRAGMENT)
    started = time.monotonic()
    with use_credentials(credentials):
        final = cast(dict[str, Any], graph.invoke(state))  # pyright: ignore[reportUnknownMemberType]
    seconds = round(time.monotonic() - started, 1)
    output = cast(dict[str, Any] | None, final.get("output"))
    if output is None:
        return FragmentResult(
            case_id=case.id,
            model=model,
            seconds=seconds,
            error=str(final.get("error")),
            direction=None,
        )
    return score(case, output, judge(case, output), model, seconds)


def render_markdown(results: list[FragmentResult]) -> str:
    """The run as a table, with what went wrong under it."""
    lines = [
        "| case | direction | passed | s |",
        "|---|---|---|---|",
        *[
            f"| {r.case_id} | {r.direction or '—'} | "
            f"{'yes' if r.passed else 'no'} | {r.seconds} |"
            for r in results
        ],
    ]
    for result in results:
        for problem in [result.error] if result.error else result.problems:
            lines.append(f"- {result.case_id}: {problem}")
    return "\n".join(lines)


def _credentials(name: str, flag: str) -> ModelCredentials:
    env = _PROVIDER_KEYS.get(name)
    if env is None:
        raise SystemExit(f"{flag} must be claude or openai, not {name!r}")
    key = os.environ.get(env, "")
    if not key:
        raise SystemExit(f"{flag} {name} needs {env} in the environment")
    return ModelCredentials(provider=name, api_key=key)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Score review_fragment.")
    parser.add_argument("--model", required=True, choices=sorted(_PROVIDER_KEYS))
    parser.add_argument(
        "--judge", choices=sorted(_PROVIDER_KEYS), help="default: the model"
    )
    parser.add_argument("--cases", nargs="*", help="case ids (default: all)")
    args = parser.parse_args(argv)

    credentials = _credentials(args.model, "--model")
    judge_name = args.judge or args.model
    judge_key = _credentials(judge_name, "--judge")
    judge_llm = get_llm(credentials=judge_key)
    judge = llm_judge(judge_llm)

    results: list[FragmentResult] = []
    for case in load_cases(args.cases):
        print(f"… {case.id} on {args.model}", flush=True)
        results.append(run_case(case, args.model, judge, credentials))

    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = RESULTS_DIR / f"{stamp}-fragments-{args.model.replace(':', '_')}.json"
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
