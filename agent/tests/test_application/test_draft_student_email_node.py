"""Tests for the draft_student_email node."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage

from src.application.graph import build_action_graph
from src.application.nodes.draft_student_email import draft_student_email
from src.application.prompts.student_email import get_system_prompt
from src.application.state import ActionState
from src.domain.action import ActionType
from tests.factories import make_state

_VALID_RESPONSE = json.dumps(
    {
        "subject": "Praca dyplomowa: co poprawić",
        "body": "Dzień dobry,\n\n1. Proszę dodać hipotezy.\n\nPozdrawiam",
    }
)


def _make_state(review_text: str = "We wstępie brakuje hipotez.") -> ActionState:
    return make_state(
        action_type=ActionType.DRAFT_STUDENT_EMAIL,
        context={
            "current_topic": "Instytucje a wzrost",
            "review_text": review_text,
            "findings": [
                {
                    "severity": "major",
                    "section": "Wstęp",
                    "description": "Brak hipotez",
                    "suggestion": "Sformułować hipotezy",
                }
            ],
            "detail": "Termin to koniec miesiąca.",
        },
    )


def test_draft_student_email_happy_path() -> None:
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_VALID_RESPONSE)

    with patch(
        "src.application.nodes.draft_student_email.get_llm", return_value=mock_llm
    ):
        result = draft_student_email(_make_state())

    output = result["output"]
    assert output is not None
    assert output["subject"] == "Praca dyplomowa: co poprawić"
    assert output["body"].startswith("Dzień dobry")
    assert result["error"] is None


def test_the_mail_is_written_from_the_review_and_the_promoters_word() -> None:
    captured: list[Any] = []

    def _capture(messages: list[Any]) -> AIMessage:
        captured.extend(messages)
        return AIMessage(content=_VALID_RESPONSE)

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = _capture

    with patch(
        "src.application.nodes.draft_student_email.get_llm", return_value=mock_llm
    ):
        draft_student_email(_make_state())

    user_content = str(captured[1].content)
    assert "We wstępie brakuje hipotez." in user_content
    assert "Sformułować hipotezy" in user_content
    assert "Termin to koniec miesiąca." in user_content


def test_without_a_review_there_is_nothing_to_write() -> None:
    mock_llm = MagicMock()

    with patch(
        "src.application.nodes.draft_student_email.get_llm", return_value=mock_llm
    ):
        result = draft_student_email(_make_state(review_text="  "))

    assert result["error"] is not None
    mock_llm.invoke.assert_not_called()


def test_a_reply_without_a_body_is_an_error() -> None:
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content='{"subject": "x", "body": " "}')

    with patch(
        "src.application.nodes.draft_student_email.get_llm", return_value=mock_llm
    ):
        result = draft_student_email(_make_state())

    assert result["error"] is not None


def test_the_prompt_keeps_the_assessment_with_the_supervisor() -> None:
    prompt = get_system_prompt("pl")

    assert "No points, percentages" in prompt
    assert "Nothing about the defence" in prompt
    assert "Never mention AI" in prompt


def test_the_action_has_a_graph() -> None:
    graph = build_action_graph(ActionType.DRAFT_STUDENT_EMAIL)

    assert "draft_student_email" in graph.nodes
