"""Tests for the draft_rubric node."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage

from src.application.nodes.draft_rubric import draft_rubric
from src.application.prompts.draft_rubric import get_system_prompt
from src.application.state import ActionState
from src.domain.action import ActionType
from tests.factories import make_state

_REPLY = json.dumps(
    {
        "elements": "### Wstęp\n- cel pracy (§ 3 ust. 2)",
        "formal": "Liczby są w progach wersji.\n### Objętość\n- sugerowana (§ 4)",
        "merit": "- logiczny tok wywodu (§ 2)",
        "severity": "Interpretacja Corvusa.\n### CRITICAL — blokuje\n- brak wstępu",
        "thresholds": {
            "min_sources": 25,
            "min_foreign_sources": 4,
            "min_body_chars": 80000,
            "max_body_chars": 130000,
        },
        "doubts": ["Załącznik nr 3 nie został dołączony."],
    }
)


def _state(**context: Any) -> ActionState:  # noqa: ANN401
    return make_state(
        action_type=ActionType.DRAFT_RUBRIC,
        context={
            "regulation": "§ 1. Praca dyplomowa jest pracą indywidualną.",
            "thesis_type": "bachelor",
            "university": "UE Katowice",
            **context,
        },
    )


def _run(state: ActionState, reply: str = _REPLY) -> tuple[ActionState, MagicMock]:
    llm = MagicMock()
    llm.invoke.return_value = AIMessage(content=reply)
    with patch("src.application.nodes.draft_rubric.get_llm", return_value=llm):
        return draft_rubric(state), llm


def test_a_regulation_becomes_four_sections_and_thresholds() -> None:
    result, _ = _run(_state())

    output = result["output"]
    assert output is not None
    assert output["elements"].startswith("### Wstęp")
    assert output["thresholds"]["min_sources"] == 25
    assert output["doubts"] == ["Załącznik nr 3 nie został dołączony."]
    assert result["error"] is None


def test_the_model_reads_the_regulation_and_the_kind_of_thesis() -> None:
    _, llm = _run(_state())

    sent = llm.invoke.call_args[0][0][1].content
    assert "Praca dyplomowa jest pracą indywidualną." in sent
    assert "first-cycle" in sent
    assert "UE Katowice" in sent


def test_a_published_rubric_goes_along_only_as_a_model_of_the_shape() -> None:
    _, llm = _run(_state(example_rubric="## Elementy pracy\n- wzór"))

    system = llm.invoke.call_args[0][0][0].content
    assert "<example_rubric>" in system
    assert "take nothing from it" in system
    assert "<example_rubric>" not in get_system_prompt(None)


def test_a_regulation_without_text_is_refused_before_the_model() -> None:
    result, llm = _run(_state(regulation="   "))

    assert result["error"] is not None
    llm.invoke.assert_not_called()


def test_a_reply_missing_a_section_fails_the_draft() -> None:
    broken = json.dumps({**json.loads(_REPLY), "severity": ""})

    result, _ = _run(_state(), reply=broken)

    assert result["error"] is not None
    assert result["output"] is None


def test_a_usual_masters_thesis_is_not_asked_for_as_an_article() -> None:
    _, llm = _run(_state(thesis_type="master"))

    sent = llm.invoke.call_args[0][0][1].content
    assert "not a research article" in sent


def test_a_length_in_pages_is_left_out_of_the_thresholds() -> None:
    """Code measures characters; a page count converted by the model is a guess."""
    system = get_system_prompt(None)

    assert "pages" in system
    assert "NOT converted" in system
