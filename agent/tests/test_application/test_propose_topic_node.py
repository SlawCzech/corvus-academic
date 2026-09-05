"""Tests for the propose_topic node."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage

from src.application.nodes.propose_topic import propose_topic
from src.application.state import ActionState
from src.domain.action import ActionType
from tests.factories import make_state

_VALID_RESPONSE = json.dumps(
    {
        "topics": [
            {
                "title": "Instytucje nieformalne a wzrost w Europie Środkowej",
                "rationale": "Luka w badaniach porównawczych.",
                "scope": "Analiza porównawcza czterech krajów, dane 2004-2024.",
                "risks": "Dostępność danych dla mniejszych gospodarek.",
            },
            {
                "title": "Kapitał społeczny a przedsiębiorczość",
                "rationale": "Dobre dane BAEL.",
                "scope": "Regresja przekrojowa na danych GUS.",
                "risks": "Endogeniczność.",
            },
        ],
        "recommended": 1,
    }
)


def _make_state(**context: Any) -> ActionState:  # noqa: ANN401
    base: dict[str, Any] = {
        "field_of_study": "Ekonomia",
        "thesis_type": "bachelor",
    }
    base.update(context)
    return make_state(action_type=ActionType.PROPOSE_TOPIC, context=base)


def test_propose_topic_happy_path() -> None:
    """Node fills output with the proposals and leaves no error."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_VALID_RESPONSE)

    with patch("src.application.nodes.propose_topic.get_llm", return_value=mock_llm):
        result = propose_topic(_make_state())

    output = result["output"]
    assert output is not None
    assert len(output["topics"]) == 2
    assert output["recommended"] == 1
    assert result["status"] == "proposed"
    assert result["error"] is None


def test_propose_topic_api_error() -> None:
    """Node records the error instead of raising, leaving output empty."""
    mock_llm: Any = MagicMock()
    mock_llm.invoke.side_effect = Exception("API timeout")

    with patch("src.application.nodes.propose_topic.get_llm", return_value=mock_llm):
        result = propose_topic(_make_state())

    assert result["error"] is not None
    assert result["output"] is None


def test_propose_topic_accepts_fenced_json() -> None:
    """Models like to wrap JSON in markdown; that must not fail the action."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content=f"```json\n{_VALID_RESPONSE}\n```"
    )

    with patch("src.application.nodes.propose_topic.get_llm", return_value=mock_llm):
        result = propose_topic(_make_state())

    assert result["error"] is None
    assert result["output"] is not None


def test_empty_proposal_is_an_error() -> None:
    """An action that proposed nothing has not succeeded."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content='{"topics": []}')

    with patch("src.application.nodes.propose_topic.get_llm", return_value=mock_llm):
        result = propose_topic(_make_state())

    assert result["error"] is not None
    assert result["output"] is None


def test_out_of_range_recommendation_falls_back_to_the_first() -> None:
    """The index comes from a language model, so it is not to be trusted."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content=json.dumps({"topics": [{"title": "Jeden temat"}], "recommended": 7})
    )

    with patch("src.application.nodes.propose_topic.get_llm", return_value=mock_llm):
        result = propose_topic(_make_state())

    output = result["output"]
    assert output is not None
    assert output["recommended"] == 0


def test_supervisor_context_reaches_the_prompt() -> None:
    """What the promoter typed, and where the student already is, must be sent."""
    captured: list[Any] = []

    def _capture(messages: list[Any]) -> AIMessage:
        captured.extend(messages)
        return AIMessage(content=_VALID_RESPONSE)

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = _capture

    state = _make_state(
        current_topic="Coś o instytucjach",
        detail="Proszę o temat z komponentem ilościowym",
        recent_notes=["Student chce pracować na danych GUS"],
    )
    with patch("src.application.nodes.propose_topic.get_llm", return_value=mock_llm):
        propose_topic(state)

    user_content = str(captured[1].content)
    assert "Coś o instytucjach" in user_content
    assert "komponentem ilościowym" in user_content
    assert "danych GUS" in user_content
    assert "Ekonomia" in user_content


def test_language_selects_the_prompt_language() -> None:
    """The output language is a top-level state field, not part of context."""
    captured: list[Any] = []

    def _capture(messages: list[Any]) -> AIMessage:
        captured.extend(messages)
        return AIMessage(content=_VALID_RESPONSE)

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = _capture

    state = make_state(
        action_type=ActionType.PROPOSE_TOPIC,
        context={"field_of_study": "Ekonomia"},
        language="en",
    )
    with patch("src.application.nodes.propose_topic.get_llm", return_value=mock_llm):
        propose_topic(state)

    assert "in English" in str(captured[0].content)
