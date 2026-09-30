"""LLM as a judge: which finding names which planted defect.

Matching a finding to an expected issue is the one step that cannot be a
string comparison — "brak hipotez badawczych" and "the introduction states no
hypothesis" are the same defect. So one model call per case maps every
expected issue, and every must-not-flag claim, to the finding numbers that
express it. Everything computed from that mapping is plain Python
(`metrics.py`), so the judge's only job is the part only a model can do.

Use a judge at least as strong as the model under test; a judge that misses
matches makes every model look worse, and the same one makes them all look
worse by a different amount.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, cast

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, TypeAdapter

from src.application.structured import invoke_structured
from src.domain.analysis import Finding

from .dataset import EvalCase

_SYSTEM_PROMPT = """You grade an automated thesis review against an answer key.

You get a numbered list of FINDINGS the review produced, a list of EXPECTED
issues (defects planted in the thesis), and a list of FALSE CLAIMS (things that
are NOT true of the thesis).

For each expected issue, list the numbers of the findings that describe that
same defect — the same underlying problem, in any language or wording. A
finding that only touches the same section but names a different problem does
not match. A finding may match more than one expected issue.

For each false claim, list the numbers of the findings that assert it (or
something that implies it).

Return ONLY a raw JSON object, no markdown, in exactly this shape:
{
  "expected": {"<expected id>": [<finding numbers>], ...},
  "false_claims": {"<false claim number>": [<finding numbers>], ...}
}
Include every expected id and every false claim number, with [] when nothing
matches."""


@dataclass(frozen=True)
class Judgement:
    """Which findings matched which expected issue and which false claim."""

    expected: dict[str, list[int]] = field(default_factory=dict[str, list[int]])
    false_claims: dict[int, list[int]] = field(default_factory=dict[int, list[int]])


Judge = Callable[[EvalCase, Sequence[Finding]], Judgement]


class _JudgeReply(BaseModel):
    expected: dict[str, list[int]] = {}
    false_claims: dict[str, list[int]] = {}


_REPLY = TypeAdapter(_JudgeReply)


def render_findings(findings: Sequence[Finding]) -> str:
    """Findings numbered from 1, as the judge refers to them."""
    return "\n".join(
        f"{i}. [{f.severity}] ({f.source or 'unknown'}) {f.section}: "
        f"{f.description}"
        for i, f in enumerate(findings, start=1)
    )


def _user_prompt(case: EvalCase, findings: Sequence[Finding]) -> str:
    expected = "\n".join(f"- {e.id}: {e.issue}" for e in case.expected)
    false_claims = "\n".join(
        f"{i}. {claim}" for i, claim in enumerate(case.must_not_flag, start=1)
    )
    return (
        f"FINDINGS:\n{render_findings(findings) or '(none)'}\n\n"
        f"EXPECTED:\n{expected}\n\n"
        f"FALSE CLAIMS:\n{false_claims or '(none)'}"
    )


def _numbers(value: Any, upper: int) -> list[int]:  # noqa: ANN401
    """Finding numbers from the judge, dropping any it made up."""
    if not isinstance(value, list):
        return []
    out: list[int] = []
    for item in cast(list[Any], value):
        try:
            n = int(item)
        except (TypeError, ValueError):
            continue
        if 1 <= n <= upper and n not in out:
            out.append(n)
    return out


def parse_judgement(
    data: dict[str, Any], case: EvalCase, finding_count: int
) -> Judgement:
    """Validate a judge's reply against the case: known ids, real numbers."""
    raw_expected = data.get("expected")
    expected_map = (
        cast(dict[str, Any], raw_expected) if isinstance(raw_expected, dict) else {}
    )
    raw_false = data.get("false_claims")
    false_map = cast(dict[str, Any], raw_false) if isinstance(raw_false, dict) else {}
    return Judgement(
        expected={
            e.id: _numbers(expected_map.get(e.id), finding_count)
            for e in case.expected
        },
        false_claims={
            i: _numbers(false_map.get(str(i)), finding_count)
            for i in range(1, len(case.must_not_flag) + 1)
        },
    )


def llm_judge(llm: BaseChatModel) -> Judge:
    """A judge backed by a chat model."""

    def judge(case: EvalCase, findings: Sequence[Finding]) -> Judgement:
        if not findings:
            return parse_judgement({}, case, 0)
        reply = invoke_structured(
            llm,
            [
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(content=_user_prompt(case, findings)),
            ],
            _REPLY,
            node="eval_judge",
        )
        return parse_judgement(reply.model_dump(), case, len(findings))

    return judge
