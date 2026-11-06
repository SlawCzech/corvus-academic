"""Eval for `draft_rubric`: does the model read a regulation the way we did?

The two cases are UE Katowice's annexes to Zarządzenie 117/22, the files
`app` seeds, and the answer key is the rubric written from each by hand
(`app/scripts/seed_data/guidelines/`). A draft does not have to match it
word for word; it has to hold the same rules, invent none, keep the
thresholds out of the text and get them right in the numbers.

Code checks the shape and the numbers. One judge call per case reads what a
regular expression cannot: which rules of the key the draft misses, which of
its rules the regulation does not say, and whether it turns "questions or
hypotheses" into a demand for both.

As in `app`, each draft gets the other set's rubric as a model of the shape.

    uv run python -m evals.rubric --model claude
    uv run python -m evals.rubric --model claude --cases bachelor
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
import zipfile
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from xml.etree import ElementTree

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, TypeAdapter

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

from .dataset import RUBRICS_DIR, rubric_sections

RESULTS_DIR = Path(__file__).parent / "results"

_PROVIDER_KEYS = {"claude": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}

_SECTIONS = ("elements", "formal", "merit", "severity")

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@dataclass(frozen=True)
class RubricCase:
    """One regulation, and what a good rubric of it holds."""

    id: str
    regulation_file: str
    # The thresholds `app/scripts/seed_data` publishes for this set.
    thresholds: dict[str, int]
    set_name: str

    def regulation(self) -> str:
        return docx_text(RUBRICS_DIR / self.regulation_file)

    def key(self) -> dict[str, str]:
        return rubric_sections(self.id)


CASES = {
    "bachelor": RubricCase(
        id="bachelor",
        regulation_file="zarzadzenie_117_22_zal_1.docx",
        thresholds={
            "min_sources": 25,
            "min_foreign_sources": 4,
            "min_body_chars": 80_000,
            "max_body_chars": 130_000,
        },
        set_name="Prace licencjackie (zarządzenie 117/22, zał. 1)",
    ),
    "master_article": RubricCase(
        id="master_article",
        regulation_file="zarzadzenie_117_22_zal_2.docx",
        thresholds={
            "min_sources": 40,
            "min_foreign_sources": 8,
            "min_body_chars": 55_000,
            "max_body_chars": 65_000,
        },
        set_name="Prace magisterskie — forma artykułu (zarządzenie 117/22, zał. 2)",
    ),
}


def docx_text(path: Path) -> str:
    """A .docx file's paragraphs, one per line — enough for a regulation."""
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))  # noqa: S314
    paragraphs = (
        "".join(node.text or "" for node in p.iter(f"{_W}t"))
        for p in root.iter(f"{_W}p")
    )
    return "\n".join(p for p in paragraphs if p.strip())


def example_for(case: RubricCase) -> str:
    """The other set's rubric, as `app` would send it."""
    other = next(c for c in CASES.values() if c.id != case.id)
    return (RUBRICS_DIR / f"{other.id}.md").read_text("utf-8")


def _threshold_numbers(thresholds: dict[str, int]) -> list[re.Pattern[str]]:
    """Each threshold as it might be written in Polish text."""
    patterns: list[re.Pattern[str]] = []
    for value in thresholds.values():
        if value >= 1000:
            thousands = value // 1000
            patterns.append(re.compile(rf"\b{thousands}[  ]?000\b|\b{thousands} tys"))
        else:
            patterns.append(re.compile(rf"\b{value}\s+pozycj"))
    return patterns


def plain_checks(case: RubricCase, output: dict[str, Any]) -> list[str]:
    """What is wrong that needs no model to see."""
    problems: list[str] = []
    for section in _SECTIONS:
        text = str(output.get(section) or "")
        if not text.strip():
            problems.append(f"{section}: empty")
        if re.search(r"^#{1,2}\s", text, re.MULTILINE):
            problems.append(f"{section}: a # or ## heading would break the sections")
    found = cast(dict[str, Any], output.get("thresholds") or {})
    for name, expected in case.thresholds.items():
        if found.get(name) != expected:
            problems.append(f"threshold {name}: {found.get(name)} (want {expected})")
    text = "\n".join(str(output.get(s) or "") for s in ("elements", "formal", "merit"))
    for pattern in _threshold_numbers(case.thresholds):
        if match := pattern.search(text):
            problems.append(f"a threshold in the text: {match.group()!r}")
    severity = str(output.get("severity") or "")
    for level in ("CRITICAL", "MAJOR", "MINOR"):
        if not re.search(rf"^###\s+{level}\b", severity, re.MULTILINE):
            problems.append(f"severity: no ### {level} heading")
    if "§" not in str(output.get("elements") or ""):
        problems.append("elements: no paragraph references")
    return problems


_JUDGE_PROMPT = """You grade a rubric an automated assistant drafted from a
university's regulation on diploma theses. You get the REGULATION, the KEY (a
rubric a person wrote from the same regulation) and the DRAFT. Both rubrics
have four sections: elements of the thesis, formal rules, what the thesis
must show, and the severity of shortfalls (the last is an interpretation; the
regulation does not grade anything).

Report:
- `missing`: rules of the KEY's first three sections that the DRAFT does not
  state in any wording. Only real rules — a required part, what a part must
  contain, a formal or substantive requirement. Not formatting, not order.
- `invented`: rules in the DRAFT's first three sections that the REGULATION
  does not say. A reasonable restatement is not invented; a requirement that
  is not in the text is.
- `both_required`: true when the DRAFT, anywhere, treats research questions
  and hypotheses as both required, or makes a missing hypothesis a defect in a
  thesis that has research questions. The regulation asks for one or the
  other.
- `suggested_as_required`: true when the DRAFT presents the length, which the
  regulation only suggests, as a hard requirement.

Each item of `missing` and `invented` is one short sentence.
Return ONLY a raw JSON object, no markdown:
{"missing": [str], "invented": [str], "both_required": bool,
 "suggested_as_required": bool}"""


class JudgeReply(BaseModel):
    missing: list[str] = Field(default_factory=list[str])
    invented: list[str] = Field(default_factory=list[str])
    both_required: bool = False
    suggested_as_required: bool = False


_REPLY = TypeAdapter(JudgeReply)

Judge = Callable[[RubricCase, dict[str, Any]], JudgeReply]


def _as_rubric(sections: dict[str, Any]) -> str:
    return "\n\n".join(f"[{s}]\n{sections.get(s) or ''}" for s in _SECTIONS)


def llm_judge(llm: BaseChatModel) -> Judge:
    """A judge backed by a model."""

    def judge(case: RubricCase, output: dict[str, Any]) -> JudgeReply:
        message = (
            f"REGULATION:\n{case.regulation()}\n\n"
            f"KEY:\n{_as_rubric(dict(case.key()))}\n\n"
            f"DRAFT:\n{_as_rubric(output)}"
        )
        return invoke_structured(
            llm,
            [
                SystemMessage(content=_JUDGE_PROMPT),  # type: ignore[attr-defined]
                HumanMessage(content=message),
            ],
            _REPLY,
            node="rubric_judge",
        )

    return judge


@dataclass
class RubricResult:
    """One regulation, one model, one run."""

    case_id: str
    model: str
    seconds: float
    error: str | None
    problems: list[str] = field(default_factory=list[str])
    missing: list[str] = field(default_factory=list[str])
    invented: list[str] = field(default_factory=list[str])
    doubts: list[str] = field(default_factory=list[str])
    output: dict[str, Any] | None = None

    @property
    def passed(self) -> bool:
        """No broken shape or number, nothing invented, at most two rules missed."""
        return (
            self.error is None
            and not self.problems
            and not self.invented
            and len(self.missing) <= 2
        )


def score(
    case: RubricCase,
    output: dict[str, Any],
    verdict: JudgeReply,
    model: str,
    seconds: float,
) -> RubricResult:
    """Everything wrong with one draft, from the checks and the judge."""
    problems = plain_checks(case, output)
    if verdict.both_required:
        problems.append("questions and hypotheses both required")
    if verdict.suggested_as_required:
        problems.append("a suggested length presented as required")
    return RubricResult(
        case_id=case.id,
        model=model,
        seconds=seconds,
        error=None,
        problems=problems,
        missing=verdict.missing,
        invented=verdict.invented,
        doubts=[str(d) for d in cast(list[Any], output.get("doubts") or [])],
        output=output,
    )


def context_for(case: RubricCase) -> dict[str, Any]:
    """The context `app` would send for this regulation."""
    return {
        "regulation": case.regulation(),
        "regulation_filename": case.regulation_file,
        "thesis_type": case.id,
        "university": "Uniwersytet Ekonomiczny w Katowicach",
        "set_name": case.set_name,
        "example_rubric": example_for(case),
    }


def run_case(
    case: RubricCase,
    model: str,
    judge: Judge,
    credentials: ModelCredentials,
) -> RubricResult:
    """Run one regulation through the real graph and score the draft."""
    state = _initial_state(
        str(uuid.uuid4()),
        ActionType.DRAFT_RUBRIC,
        "",
        context_for(case),
        model,
        "pl",
    )
    graph = build_action_graph(ActionType.DRAFT_RUBRIC)
    started = time.monotonic()
    with use_credentials(credentials):
        final = cast(dict[str, Any], graph.invoke(state))  # pyright: ignore[reportUnknownMemberType]
    seconds = round(time.monotonic() - started, 1)
    output = cast(dict[str, Any] | None, final.get("output"))
    if output is None:
        return RubricResult(
            case_id=case.id, model=model, seconds=seconds, error=str(final.get("error"))
        )
    return score(case, output, judge(case, output), model, seconds)


def render_markdown(results: list[RubricResult]) -> str:
    """The run as a table, with what went wrong under it."""
    lines = [
        "| case | passed | problems | missing | invented | doubts | s |",
        "|---|---|---|---|---|---|---|",
        *[
            f"| {r.case_id} | {'yes' if r.passed else 'no'} | {len(r.problems)} "
            f"| {len(r.missing)} | {len(r.invented)} | {len(r.doubts)} | {r.seconds} |"
            for r in results
        ],
    ]
    for r in results:
        if r.error:
            lines.append(f"- {r.case_id}: {r.error}")
        lines += [f"- {r.case_id}: {p}" for p in r.problems]
        lines += [f"- {r.case_id} missing: {m}" for m in r.missing]
        lines += [f"- {r.case_id} invented: {i}" for i in r.invented]
        lines += [f"- {r.case_id} doubt: {d}" for d in r.doubts]
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
    parser = argparse.ArgumentParser(description="Score draft_rubric.")
    parser.add_argument("--model", required=True, choices=sorted(_PROVIDER_KEYS))
    parser.add_argument(
        "--judge", choices=sorted(_PROVIDER_KEYS), help="default: the model"
    )
    parser.add_argument("--cases", nargs="*", choices=sorted(CASES))
    args = parser.parse_args(argv)

    credentials = _credentials(args.model, "--model")
    judge_name = args.judge or args.model
    judge = llm_judge(get_llm(credentials=_credentials(judge_name, "--judge")))

    results: list[RubricResult] = []
    for case_id in args.cases or sorted(CASES):
        print(f"… {case_id} on {args.model}", flush=True)
        results.append(run_case(CASES[case_id], args.model, judge, credentials))

    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = RESULTS_DIR / f"{stamp}-rubric-{args.model}.json"
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
