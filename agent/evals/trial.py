"""Eval for what a promoter acts on: the trial review's advice, and the mail.

`run.py` scores the findings, which both reviews share. What differs is the last
step, and a promoter who forwards it has no second reader: advice nobody can act
on, or a mail that says more than the review did, reaches the student as it is.

    uv run python -m evals.trial --model claude
    uv run python -m evals.trial --model claude --cases pokolenie-z

Uses the three thesis cases. One run is the whole trial graph, then the mail from
its result, the way `app` hands it over. Two judge calls read the two texts.
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
from src.domain.analysis import FindingSeverity
from src.infrastructure.llm_factory import (
    ModelCredentials,
    get_llm,
    use_credentials,
)

from .dataset import EvalCase, load_cases

RESULTS_DIR = Path(__file__).parent / "results"

_PROVIDER_KEYS = {"claude": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}
_LOCAL_JUDGE = "qwen3:30b-a3b"

MAX_POINTS = 5

_FORBIDDEN_IN_MAIL = re.compile(
    r"\bAI\b|sztuczn\w+ inteligencj\w+|\bmodel\w* językow\w+|automatyczn\w+ anali"
    r"|recenzj\w+ próbn\w+|\b\d+\s*(?:/\s*10|pkt\b|punkt(?:ów|y)?\b)"
    r"|\bobron\w*\b|krytyczn\w+ uwag\w+|\bMAJOR\b|\bCRITICAL\b|\bMINOR\b"
    r"|\*\*|^#+\s",
    re.IGNORECASE | re.MULTILINE,
)
_NUMBERED_POINT = re.compile(r"^\s*\d+[.)]\s", re.MULTILINE)


def serious_issues(case: EvalCase) -> tuple[str, ...]:
    """The planted defects a thesis cannot be submitted with."""
    return tuple(
        e.issue
        for e in case.expected
        if e.severity in (FindingSeverity.CRITICAL, FindingSeverity.MAJOR)
    )


def mail_problems(body: str) -> list[str]:
    """What a mail must not do, wherever it can be seen without a model."""
    problems = [
        f"forbidden: {m.group(0).strip()}" for m in _FORBIDDEN_IN_MAIL.finditer(body)
    ]
    points = len(_NUMBERED_POINT.findall(body))
    if points == 0:
        problems.append("no numbered corrections")
    if points > MAX_POINTS:
        problems.append(f"{points} points, limit {MAX_POINTS}")
    if not body.lstrip().startswith("Dzień dobry"):
        problems.append("does not open with the greeting")
    if not body.rstrip().endswith("Pozdrawiam"):
        problems.append("does not end on the sign-off")
    return problems


_TRIAL_JUDGE = """You grade a trial review a supervisor will act on, before the \
thesis is submitted. You get the REVIEW and a numbered list of DEFECTS the thesis \
really has.

For each defect answer whether the review ACTS on it: it says where in the thesis \
the problem is and what the author should do, concretely enough to start work \
without asking. Naming the problem with no way forward is false. "Należy poprawić \
metodologię" is false; "w rozdziale 2 opisać, jak dobrano respondentów" is true.

first_is_most_important: true when the correction the review puts first is among \
the most serious things it raises.
generic: quote every recommendation in the review that would fit any thesis. \
Empty when there are none.

Return ONLY a raw JSON object, no markdown, in exactly this shape:
{"acts_on": {"1": true}, "first_is_most_important": true, "generic": []}"""

_MAIL_JUDGE = """You grade a mail a thesis supervisor is about to send a student. \
You get the REVIEW and the FINDINGS the mail was written from, and the MAIL.

added: quote every claim about the thesis, or requirement, that is in the MAIL \
and has no basis in the REVIEW or the FINDINGS. Rewording is fine; new facts are \
not.
actionable: true when the student could start on the corrections from the mail \
alone, without seeing the review.
respectful: true when it reads as a supervisor helping someone finish, without \
scolding and without empty praise.
gendered: quote every word that gives away the gender of the student or of the \
supervisor, such as Pan, Pani, przeczytałem or przeczytałam. Empty when there are \
none.

Return ONLY a raw JSON object, no markdown, in exactly this shape:
{"added": [], "actionable": true, "respectful": true, "gendered": []}"""


class TrialVerdict(BaseModel):
    acts_on: dict[str, bool] = {}
    first_is_most_important: bool = False
    generic: list[str] = []


class MailVerdict(BaseModel):
    added: list[str] = []
    actionable: bool = False
    respectful: bool = False
    gendered: list[str] = []


_TRIAL_REPLY = TypeAdapter(TrialVerdict)
_MAIL_REPLY = TypeAdapter(MailVerdict)


def judge_trial(
    llm: BaseChatModel, review: str, issues: tuple[str, ...]
) -> TrialVerdict:
    numbered = "\n".join(f"{i}. {issue}" for i, issue in enumerate(issues, 1))
    return invoke_structured(
        llm,
        [
            SystemMessage(content=_TRIAL_JUDGE),  # type: ignore[attr-defined]
            HumanMessage(content=f"REVIEW:\n{review}\n\nDEFECTS:\n{numbered}"),
        ],
        _TRIAL_REPLY,
        node="trial_judge",
    )


def judge_mail(
    llm: BaseChatModel, review: str, findings: list[dict[str, Any]], mail: str
) -> MailVerdict:
    message = (
        f"REVIEW:\n{review}\n\n"
        f"FINDINGS:\n{json.dumps(findings, ensure_ascii=False)}\n\n"
        f"MAIL:\n{mail}"
    )
    return invoke_structured(
        llm,
        [
            SystemMessage(content=_MAIL_JUDGE),  # type: ignore[attr-defined]
            HumanMessage(content=message),
        ],
        _MAIL_REPLY,
        node="mail_judge",
    )


def trial_problems(verdict: TrialVerdict, issues: tuple[str, ...]) -> list[str]:
    """What the judge found wrong with the advice."""
    problems = [
        f"no way forward: {issue}"
        for i, issue in enumerate(issues, 1)
        if not verdict.acts_on.get(str(i), False)
    ]
    if not verdict.first_is_most_important:
        problems.append("the first correction is not among the most serious")
    problems += [f"generic: {quote}" for quote in verdict.generic]
    return problems


def mail_verdict_problems(verdict: MailVerdict) -> list[str]:
    """What the judge found wrong with the mail."""
    problems = [f"added: {quote}" for quote in verdict.added]
    problems += [f"gendered: {quote}" for quote in verdict.gendered]
    if not verdict.actionable:
        problems.append("the student could not act on it")
    if not verdict.respectful:
        problems.append("the tone is off")
    return problems


@dataclass
class TrialResult:
    """One thesis: its trial review, the mail from it, what was wrong with each."""

    case_id: str
    model: str
    seconds: float
    error: str | None = None
    review: str = ""
    mail: dict[str, Any] | None = None
    review_problems: list[str] = field(default_factory=list[str])
    mail_problems: list[str] = field(default_factory=list[str])

    @property
    def passed(self) -> bool:
        return (
            self.error is None and not self.review_problems and not self.mail_problems
        )


def _run_graph(
    action_type: ActionType, case_id: str, context: dict[str, Any], model: str
) -> dict[str, Any]:
    state = _initial_state(
        str(uuid.uuid4()), action_type, f"eval-{case_id}", context, model, "pl"
    )
    graph = build_action_graph(action_type)
    return cast(dict[str, Any], graph.invoke(state))  # pyright: ignore[reportUnknownMemberType]


def _finding_dict(finding: Any) -> dict[str, Any]:  # noqa: ANN401
    return {
        "severity": str(finding.severity),
        "section": finding.section,
        "description": finding.description,
        "suggestion": finding.suggestion,
    }


def run_case(
    case: EvalCase,
    model: str,
    judge_llm: BaseChatModel,
    credentials: ModelCredentials | None = None,
) -> TrialResult:
    """The trial review, then the mail from its result, both judged."""
    started = time.monotonic()
    with use_credentials(credentials):
        trial = _run_graph(ActionType.TRIAL_REVIEW, case.id, case.context(), model)
        output = cast(dict[str, Any] | None, trial.get("output"))
        if output is None:
            return TrialResult(
                case_id=case.id,
                model=model,
                seconds=round(time.monotonic() - started, 1),
                error=str(trial.get("error")),
            )
        review = str(output.get("summary", ""))
        findings = [_finding_dict(f) for f in trial.get("findings", [])]
        mail_state = _run_graph(
            ActionType.DRAFT_STUDENT_EMAIL,
            case.id,
            {
                "current_topic": case.metadata.get("title"),
                "review_text": review,
                "findings": findings,
            },
            model,
        )
    seconds = round(time.monotonic() - started, 1)
    mail = cast(dict[str, Any] | None, mail_state.get("output"))
    if mail is None:
        return TrialResult(
            case_id=case.id,
            model=model,
            seconds=seconds,
            review=review,
            error=str(mail_state.get("error")),
        )
    issues = serious_issues(case)
    body = str(mail.get("body", ""))
    return TrialResult(
        case_id=case.id,
        model=model,
        seconds=seconds,
        review=review,
        mail=mail,
        review_problems=trial_problems(judge_trial(judge_llm, review, issues), issues),
        mail_problems=[
            *mail_problems(body),
            *mail_verdict_problems(judge_mail(judge_llm, review, findings, body)),
        ],
    )


def render_markdown(results: list[TrialResult]) -> str:
    """The run as a table, with what went wrong under it."""
    lines = [
        "| case | advice | mail | s |",
        "|---|---|---|---|",
        *[
            f"| {r.case_id} | {'yes' if not r.review_problems else 'no'} "
            f"| {'yes' if r.mail and not r.mail_problems else 'no'} | {r.seconds} |"
            for r in results
        ],
    ]
    for result in results:
        if result.error:
            lines.append(f"- {result.case_id}: {result.error}")
        for problem in [*result.review_problems, *result.mail_problems]:
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
    parser = argparse.ArgumentParser(description="Score trial advice and the mail.")
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

    results: list[TrialResult] = []
    for case in load_cases(args.cases):
        print(f"… {case.id} on {args.model}", flush=True)
        results.append(run_case(case, args.model, judge_llm, credentials))

    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = RESULTS_DIR / f"{stamp}-trial-{args.model.replace(':', '_')}.json"
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
