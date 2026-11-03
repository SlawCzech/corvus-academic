"""Tests for structured replies: constrained where possible, repaired when not."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.application.replies import FINDINGS, REVIEW, TOPIC_PROPOSAL
from src.application.structured import StructuredOutputError, invoke_structured

_FINDING = (
    '[{"section": "Wstęp", "description": "Brak hipotez", '
    '"severity": "critical", "suggestion": "Dodać hipotezy."}]'
)


def _llm(*replies: str) -> MagicMock:
    llm = MagicMock()
    llm.invoke.side_effect = [AIMessage(content=r) for r in replies]
    return llm


def test_a_valid_reply_is_parsed_on_the_first_call() -> None:
    llm = _llm(_FINDING)

    findings = invoke_structured(llm, [HumanMessage("x")], FINDINGS, node="t")

    assert findings[0].severity == "critical"
    assert llm.invoke.call_count == 1


def test_a_fenced_reply_is_accepted() -> None:
    llm = _llm(f"```json\n{_FINDING}\n```")

    assert invoke_structured(llm, [HumanMessage("x")], FINDINGS, node="t")


def test_an_invalid_reply_gets_one_repair_turn_with_the_error() -> None:
    bad = '[{"section": "Wstęp", "description": "x", "severity": "fatal"}]'
    llm = _llm(bad, _FINDING)

    findings = invoke_structured(llm, [HumanMessage("x")], FINDINGS, node="t")

    assert len(findings) == 1
    repair: list[Any] = llm.invoke.call_args_list[1].args[0]
    # The model sees what it said and exactly what was wrong with it.
    assert repair[-2].content == bad
    assert "0.severity" in repair[-1].content
    assert "0.suggestion" in repair[-1].content


def test_the_reply_goes_back_into_the_repair_turn_unchanged() -> None:
    """Claude's reasoning parts stay with the turn that is shown to it again."""
    parts: list[str | dict[str, Any]] = [
        {"type": "thinking", "thinking": "", "signature": "EvEC"},
        {"type": "text", "text": "not json"},
    ]
    first = AIMessage(content=parts)
    llm = MagicMock()
    llm.invoke.side_effect = [first, AIMessage(content=_FINDING)]

    invoke_structured(llm, [HumanMessage("x")], FINDINGS, node="t")

    assert llm.invoke.call_args_list[1].args[0][-2] is first


def test_a_refusal_is_not_asked_to_fix_its_json() -> None:
    declined = AIMessage(content="", response_metadata={"stop_reason": "refusal"})
    llm = MagicMock()
    llm.invoke.return_value = declined

    with pytest.raises(StructuredOutputError, match="declined"):
        invoke_structured(llm, [HumanMessage("x")], FINDINGS, node="t")

    assert llm.invoke.call_count == 1


def test_broken_json_is_repaired_too() -> None:
    llm = _llm('[{"section": "Wstęp"', _FINDING)

    assert invoke_structured(llm, [HumanMessage("x")], FINDINGS, node="t")
    assert "Invalid JSON" in llm.invoke.call_args_list[1].args[0][-1].content


def test_a_reply_that_stays_wrong_raises() -> None:
    llm = _llm("nope", "still nope")

    with pytest.raises(StructuredOutputError, match="2 attempts"):
        invoke_structured(llm, [HumanMessage("x")], FINDINGS, node="t")


def test_other_backends_get_no_format_argument() -> None:
    llm = _llm(_FINDING)

    invoke_structured(llm, [HumanMessage("x")], FINDINGS, node="t")

    assert llm.invoke.call_args.kwargs == {}


# ---------- the reply shapes ----------


def test_severity_is_case_insensitive() -> None:
    reply = FINDINGS.validate_json(_FINDING.replace("critical", " Critical "))

    assert reply[0].severity == "critical"


def test_review_accepts_the_synonyms_models_reach_for() -> None:
    reply = REVIEW.validate_python(
        {
            "scores": [{"criterion": "Struktura", "score": 7, "max": 10}],
            "summary": "Praca spełnia wymagania.",
            "decision": "Dopuścić do obrony",
        }
    )

    assert reply.scores[0].criteria == "Struktura"
    assert reply.scores[0].points == 7
    assert reply.review_text == "Praca spełnia wymagania."


def test_review_rejects_points_outside_the_scale() -> None:
    with pytest.raises(ValueError, match="less than or equal to 10"):
        REVIEW.validate_python(
            {
                "scores": [{"criteria": "Struktura", "points": 70}],
                "review_text": "x",
                "recommendation": "y",
            }
        )


def test_whitespace_is_not_text() -> None:
    with pytest.raises(ValueError, match="at least 1 character"):
        TOPIC_PROPOSAL.validate_python({"topics": [{"title": "   "}]})
