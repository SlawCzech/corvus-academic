"""Tests for the draft_meeting_note node."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage

from src.application.nodes.draft_meeting_note import draft_meeting_note
from src.application.state import ActionState
from src.domain.action import ActionType
from tests.factories import make_state

_VALID_RESPONSE = json.dumps(
    {
        "content": "Omówiliśmy zakres rozdziału metodologicznego. "
        "Student przedstawi projekt badawczy do 15 marca.",
        "topics_discussed": ["Zakres rozdziału 2", "Dobór próby"],
        "agreed_actions": ["Projekt badawczy do 15 marca"],
    }
)


def _make_state(detail: str = "rozdział 2, dobór próby, termin 15.03") -> ActionState:
    return make_state(
        action_type=ActionType.DRAFT_MEETING_NOTE,
        context={
            "detail": detail,
            "current_topic": "Instytucje a wzrost",
            "recent_notes": ["Ustaliliśmy temat pracy"],
        },
    )


def test_draft_meeting_note_happy_path() -> None:
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_VALID_RESPONSE)

    with patch(
        "src.application.nodes.draft_meeting_note.get_llm", return_value=mock_llm
    ):
        result = draft_meeting_note(_make_state())

    output = result["output"]
    assert output is not None
    assert output["content"].startswith("Omówiliśmy")
    assert output["agreed_actions"] == ["Projekt badawczy do 15 marca"]
    assert result["error"] is None


def test_draft_meeting_note_api_error() -> None:
    mock_llm: Any = MagicMock()
    mock_llm.invoke.side_effect = Exception("API timeout")

    with patch(
        "src.application.nodes.draft_meeting_note.get_llm", return_value=mock_llm
    ):
        result = draft_meeting_note(_make_state())

    assert result["error"] is not None
    assert result["output"] is None


def test_nothing_to_write_up_is_refused() -> None:
    """The node writes up the promoter's notes; it does not invent a meeting."""
    mock_llm = MagicMock()

    with patch(
        "src.application.nodes.draft_meeting_note.get_llm", return_value=mock_llm
    ):
        result = draft_meeting_note(_make_state(detail="  "))

    assert result["error"] is not None
    mock_llm.invoke.assert_not_called()


def test_empty_note_is_an_error() -> None:
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content='{"content": "   "}')

    with patch(
        "src.application.nodes.draft_meeting_note.get_llm", return_value=mock_llm
    ):
        result = draft_meeting_note(_make_state())

    assert result["error"] is not None


def test_earlier_notes_are_sent_for_continuity() -> None:
    captured: list[Any] = []

    def _capture(messages: list[Any], **_: Any) -> AIMessage:  # noqa: ANN401
        captured.extend(messages)
        return AIMessage(content=_VALID_RESPONSE)

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = _capture

    with patch(
        "src.application.nodes.draft_meeting_note.get_llm", return_value=mock_llm
    ):
        draft_meeting_note(_make_state())

    user_content = str(captured[1].content)
    assert "dobór próby" in user_content
    assert "Ustaliliśmy temat pracy" in user_content
