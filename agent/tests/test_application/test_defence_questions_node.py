"""Tests for the defence_questions node."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage

from src.application.nodes.defence_questions import defence_questions
from src.application.prompts.defence_questions import MAX_WORDS, get_system_prompt
from src.application.state import ActionState
from src.domain.action import ActionType
from tests.factories import make_state

_VALID_RESPONSE = json.dumps(
    {
        "questions": [
            {"question": "Co było celem pracy o instytucjach i wzroście?"},
            {"question": "Dlaczego wybrano akurat tę metodę badania wzrostu?"},
            {"question": "Na ile wnioski o instytucjach można uogólnić?"},
        ]
    }
)


def _make_state(
    text: str = "Rozdział 1: Wstęp. Rozdział 2: Metodologia.",
) -> ActionState:
    return make_state(
        action_type=ActionType.DEFENCE_QUESTIONS,
        context={
            "text": text,
            "current_topic": "Instytucje a wzrost",
            "field_of_study": "Ekonomia",
            "thesis_type": "bachelor",
        },
    )


def test_defence_questions_happy_path() -> None:
    """Node returns the committee's questions and no error."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_VALID_RESPONSE)

    with patch(
        "src.application.nodes.defence_questions.get_llm", return_value=mock_llm
    ):
        result = defence_questions(_make_state())

    output = result["output"]
    assert output is not None
    assert len(output["questions"]) == 3
    assert result["error"] is None


def test_a_question_is_only_its_text() -> None:
    """A model that still adds the old detail does not get it through."""
    reply = {
        "questions": [
            {
                "question": "Co było celem pracy?",
                "rationale": "Sprawdza rozumienie.",
                "section": "Wstęp",
                "focus": "problem",
            }
        ]
    }
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=json.dumps(reply))

    with patch(
        "src.application.nodes.defence_questions.get_llm", return_value=mock_llm
    ):
        result = defence_questions(_make_state())

    assert result["output"] == {"questions": [{"question": "Co było celem pracy?"}]}


def test_prompt_asks_for_short_general_questions() -> None:
    prompt = get_system_prompt()

    assert f"at most {MAX_WORDS} words" in prompt
    assert "rationale" not in prompt
    assert '"focus"' not in prompt


def test_defence_questions_api_error() -> None:
    """Node records the error instead of raising."""
    mock_llm: Any = MagicMock()
    mock_llm.invoke.side_effect = Exception("API timeout")

    with patch(
        "src.application.nodes.defence_questions.get_llm", return_value=mock_llm
    ):
        result = defence_questions(_make_state())

    assert result["error"] is not None
    assert result["output"] is None


def test_questions_without_a_thesis_are_refused() -> None:
    """There is nothing to ask about before a draft has been uploaded."""
    mock_llm = MagicMock()

    with patch(
        "src.application.nodes.defence_questions.get_llm", return_value=mock_llm
    ):
        result = defence_questions(_make_state(text="   "))

    assert result["error"] is not None
    mock_llm.invoke.assert_not_called()


def test_empty_question_list_is_an_error() -> None:
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content='{"questions": []}')

    with patch(
        "src.application.nodes.defence_questions.get_llm", return_value=mock_llm
    ):
        result = defence_questions(_make_state())

    assert result["error"] is not None
    assert result["output"] is None


def test_a_long_thesis_goes_in_whole() -> None:
    """The committee reads the whole work, and so does the model."""
    captured: list[Any] = []

    def _capture(messages: list[Any], **_: Any) -> AIMessage:  # noqa: ANN401
        captured.extend(messages)
        return AIMessage(content=_VALID_RESPONSE)

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = _capture

    with patch(
        "src.application.nodes.defence_questions.get_llm", return_value=mock_llm
    ):
        result = defence_questions(_make_state(text="x" * 40000 + " KONIEC"))

    assert result["error"] is None
    assert "x" * 40000 + " KONIEC" in str(captured[1].content)


def test_supervisor_instructions_reach_the_prompt() -> None:
    captured: list[Any] = []

    def _capture(messages: list[Any], **_: Any) -> AIMessage:  # noqa: ANN401
        captured.extend(messages)
        return AIMessage(content=_VALID_RESPONSE)

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = _capture

    state = _make_state()
    state["context"]["detail"] = "Proszę o pytanie o dobór próby"
    with patch(
        "src.application.nodes.defence_questions.get_llm", return_value=mock_llm
    ):
        defence_questions(state)

    assert "dobór próby" in str(captured[1].content)
    assert "Instytucje a wzrost" in str(captured[1].content)
