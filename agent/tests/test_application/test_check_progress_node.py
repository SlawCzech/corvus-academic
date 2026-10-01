"""Tests for the check_progress node."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage

from src.application.nodes.check_progress import check_progress
from src.application.state import ActionState
from src.domain.action import ActionType
from src.infrastructure.llm_factory import ModelCredentials, use_credentials
from tests.factories import make_state

_VALID_RESPONSE = json.dumps(
    {
        "summary": "Rozdział metodologiczny został napisany od nowa.",
        "changes": [
            {
                "area": "Metodologia",
                "change": "Dodano opis doboru próby.",
                "assessment": "progress",
            },
            {
                "area": "Wstęp",
                "change": "Poprawiono interpunkcję.",
                "assessment": "cosmetic",
            },
        ],
        "concerns": ["Nadal brak hipotez badawczych."],
        "next_steps": ["Sformułować hipotezy przed kolejnym spotkaniem."],
    }
)


def _make_state(previous: str = "Wersja 1", current: str = "Wersja 2") -> ActionState:
    return make_state(
        action_type=ActionType.CHECK_PROGRESS,
        context={
            "previous_text": previous,
            "current_text": current,
            "previous_version": 1,
            "current_version": 2,
            "current_topic": "Instytucje a wzrost",
        },
    )


def test_check_progress_happy_path() -> None:
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_VALID_RESPONSE)

    with patch("src.application.nodes.check_progress.get_llm", return_value=mock_llm):
        result = check_progress(_make_state())

    output = result["output"]
    assert output is not None
    assert len(output["changes"]) == 2
    assert output["concerns"] == ["Nadal brak hipotez badawczych."]
    assert result["error"] is None


def test_check_progress_api_error() -> None:
    mock_llm: Any = MagicMock()
    mock_llm.invoke.side_effect = Exception("API timeout")

    with patch("src.application.nodes.check_progress.get_llm", return_value=mock_llm):
        result = check_progress(_make_state())

    assert result["error"] is not None
    assert result["output"] is None


def test_a_single_version_cannot_be_compared() -> None:
    """The first upload has nothing to be compared against."""
    mock_llm = MagicMock()

    with patch("src.application.nodes.check_progress.get_llm", return_value=mock_llm):
        result = check_progress(_make_state(previous=""))

    assert result["error"] is not None
    mock_llm.invoke.assert_not_called()


def test_summary_is_required() -> None:
    """Changes without a verdict are not a progress check."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content='{"changes": []}')

    with patch("src.application.nodes.check_progress.get_llm", return_value=mock_llm):
        result = check_progress(_make_state())

    assert result["error"] is not None


def test_both_versions_reach_the_prompt() -> None:
    captured: list[Any] = []

    def _capture(messages: list[Any]) -> AIMessage:
        captured.extend(messages)
        return AIMessage(content=_VALID_RESPONSE)

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = _capture

    with patch("src.application.nodes.check_progress.get_llm", return_value=mock_llm):
        check_progress(_make_state(previous="STARA WERSJA", current="NOWA WERSJA"))

    user_content = str(captured[1].content)
    assert "STARA WERSJA" in user_content
    assert "NOWA WERSJA" in user_content
    assert "v1" in user_content and "v2" in user_content


def _sent_to(mock_llm: MagicMock) -> str:
    return str(mock_llm.invoke.call_args.args[0][1].content)


def test_the_local_model_compares_the_beginning_of_each_version() -> None:
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_VALID_RESPONSE)
    long_version = "a" * 20000 + " ANKIETA WŚRÓD NAUCZYCIELI"

    with patch("src.application.nodes.check_progress.get_llm", return_value=mock_llm):
        check_progress(_make_state(current=long_version))

    assert "ANKIETA" not in _sent_to(mock_llm)
    assert "[...text truncated...]" in _sent_to(mock_llm)


def test_a_hosted_model_compares_the_two_versions_whole() -> None:
    """What a student adds between versions is rarely on the first pages."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_VALID_RESPONSE)
    long_version = "a" * 20000 + " ANKIETA WŚRÓD NAUCZYCIELI"

    with (
        patch("src.application.nodes.check_progress.get_llm", return_value=mock_llm),
        use_credentials(ModelCredentials(provider="claude", api_key="k")),
    ):
        check_progress(_make_state(current=long_version))

    assert "ANKIETA WŚRÓD NAUCZYCIELI" in _sent_to(mock_llm)
    assert "truncated" not in _sent_to(mock_llm)
