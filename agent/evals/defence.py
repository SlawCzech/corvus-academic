"""Eval for `defence_questions`: would a committee ask this aloud?

Reuses the review's theses (`cases/`); there is no answer key, because what
matters is the kind of question and not which one. Short, single, free of
tables and page numbers: plain checks. One judge call per case reads what a
regular expression cannot: whether a student could answer aloud, whether the
question belongs to this thesis, and which part of the work it asks about.

    uv run python -m evals.defence --model claude
    uv run python -m evals.defence --model claude --cases pokolenie-z
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
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, TypeAdapter

from src.application.graph import build_action_graph
from src.application.prompts.defence_questions import MAX_WORDS, QUESTION_COUNT
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

from .dataset import EvalCase, load_cases

RESULTS_DIR = Path(__file__).parent / "results"

_PROVIDER_KEYS = {"claude": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}
_LOCAL_JUDGE = "qwen3:30b-a3b"

# A number of any kind is a thing to look up, and these are where it is looked
# up. "Tabela" with no digit counts too: the question still points at a page.
_DETAIL = re.compile(
    r"\d|\btabel\w*|\bwykres\w*|\brysun\w*|\bstr\.|\baneks\w*|\bzałącznik\w*",
    re.IGNORECASE,
)
# A second question joined by "i": the judge lets these through as one.
_SECOND_QUESTION = re.compile(
    r"\bi\s+(?:jak\w*|dlaczego|czy|na ile|co|po co|po czym|gdzie|kiedy)\b",
    re.IGNORECASE,
)


def questions_of(output: dict[str, Any]) -> list[str]:
    """The questions as text, in order."""
    questions = cast(list[dict[str, Any]], output.get("questions") or [])
    return [str(q.get("question") or "") for q in questions]


def plain_checks(output: dict[str, Any]) -> list[str]:
    """What is wrong that needs no model to see."""
    questions = questions_of(output)
    problems: list[str] = []
    if len(questions) != QUESTION_COUNT:
        problems.append(f"{len(questions)} questions")
    for i, question in enumerate(questions, 1):
        words = len(question.split())
        if words > MAX_WORDS:
            problems.append(f"question {i}: {words} words")
        if question.count("?") != 1 or _SECOND_QUESTION.search(question):
            problems.append(f"question {i}: not one question")
        if match := _DETAIL.search(question):
            problems.append(f"question {i}: points at a detail ({match.group()})")
    return problems


_JUDGE_PROMPT = """You grade questions an automated assistant drafted for a
thesis defence. They should be what a committee member actually says aloud:
general, about the work as a whole, answerable in a minute or two by a student
who wrote it, with no notes and no need to find a passage.

You get the TITLE of the thesis and numbered QUESTIONS. For each question:
- `spoken`: true when a student who understands the thesis could answer aloud
  on the spot. False when it hangs on a detail, a passage, a figure, or packs
  several questions into one.
- `this_thesis`: true when it could only be about this thesis. False when it
  would fit any thesis word for word.
- `aspect`: "aim" (what the work set out to do, why it matters), "method" (how
  it was researched, why that way), "conclusions" (what came out, how far it
  holds), or "other".

Return ONLY a raw JSON object, no markdown, in exactly this shape:
{"questions": {"1": {"spoken": true, "this_thesis": true, "aspect": "aim"}}}
Number the questions from 1; include every one."""


class QuestionVerdict(BaseModel):
    spoken: bool
    this_thesis: bool
    aspect: Literal["aim", "method", "conclusions", "other"]


class JudgeReply(BaseModel):
    questions: dict[str, QuestionVerdict] = {}


_REPLY = TypeAdapter(JudgeReply)

Judge = Callable[[EvalCase, dict[str, Any]], JudgeReply]


def llm_judge(llm: BaseChatModel) -> Judge:
    """A judge backed by a model."""

    def judge(case: EvalCase, output: dict[str, Any]) -> JudgeReply:
        numbered = "\n".join(f"{i}. {q}" for i, q in enumerate(questions_of(output), 1))
        message = f"TITLE: {case.metadata.get('title')}\n\nQUESTIONS:\n{numbered}"
        return invoke_structured(
            llm,
            [
                SystemMessage(content=_JUDGE_PROMPT),  # type: ignore[attr-defined]
                HumanMessage(content=message),
            ],
            _REPLY,
            node="defence_judge",
        )

    return judge


@dataclass
class DefenceResult:
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
    case: EvalCase,
    output: dict[str, Any],
    verdict: JudgeReply,
    model: str,
    seconds: float,
) -> DefenceResult:
    """Everything wrong with one run, from the checks and the judge's reading."""
    problems = plain_checks(output)
    aspects: list[str] = []
    for i in range(1, len(questions_of(output)) + 1):
        reading = verdict.questions.get(str(i))
        if reading is None:
            problems.append(f"question {i}: not judged")
            continue
        aspects.append(reading.aspect)
        if not reading.spoken:
            problems.append(f"question {i}: not answerable aloud")
        if not reading.this_thesis:
            problems.append(f"question {i}: fits any thesis")
    if missing := {"aim", "method", "conclusions"} - set(aspects):
        problems.append(f"nothing on: {', '.join(sorted(missing))}")
    return DefenceResult(
        case_id=case.id,
        model=model,
        seconds=seconds,
        error=None,
        problems=problems,
        output=output,
    )


def run_case(
    case: EvalCase,
    model: str,
    judge: Judge,
    credentials: ModelCredentials | None = None,
) -> DefenceResult:
    """Run one thesis through the real graph and score what comes out."""
    state = _initial_state(
        str(uuid.uuid4()),
        ActionType.DEFENCE_QUESTIONS,
        f"eval-{case.id}",
        case.context(),
        model,
        "pl",
    )
    graph = build_action_graph(ActionType.DEFENCE_QUESTIONS)
    started = time.monotonic()
    with use_credentials(credentials):
        final = cast(dict[str, Any], graph.invoke(state))  # pyright: ignore[reportUnknownMemberType]
    seconds = round(time.monotonic() - started, 1)
    output = cast(dict[str, Any] | None, final.get("output"))
    if output is None:
        return DefenceResult(
            case_id=case.id,
            model=model,
            seconds=seconds,
            error=str(final.get("error")),
        )
    return score(case, output, judge(case, output), model, seconds)


def render_markdown(results: list[DefenceResult]) -> str:
    """The run as a table, with the problems and the questions under it."""
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
    for result in results:
        lines.append(f"\n{result.case_id}:")
        lines += [f"- {q}" for q in questions_of(result.output or {})]
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
    parser = argparse.ArgumentParser(description="Score defence_questions.")
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

    results: list[DefenceResult] = []
    for case in load_cases(args.cases):
        print(f"… {case.id} on {args.model}", flush=True)
        results.append(run_case(case, args.model, judge, credentials))

    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = RESULTS_DIR / f"{stamp}-defence-{args.model.replace(':', '_')}.json"
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
