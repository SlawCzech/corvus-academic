"""Tests for the analyze_structure node."""

from typing import Any
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage

from src.application.nodes.structure import analyze_structure
from src.application.state import ActionState
from tests.factories import make_state

_VALID_RESPONSE = (
    '[{"section": "Introduction", "description": "Missing abstract",'
    ' "severity": "major", "suggestion": "Add an abstract section."}]'
)


def _make_state() -> ActionState:
    return make_state(
        context={
            "text": "Chapter 1: Introduction. Chapter 2: Methodology.",
            "guidelines": "The thesis must have at least five chapters.",
            "metadata": {
                "author": "Jan Kowalski",
                "title": "Test Thesis",
                "year": 2024,
                "field_of_study": "Computer Science",
            },
        }
    )


def test_analyze_structure_happy_path() -> None:
    """Node returns non-empty findings and no error on successful LLM call."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_VALID_RESPONSE)

    with patch("src.application.nodes.structure.get_llm", return_value=mock_llm):
        result = analyze_structure(_make_state())

    assert len(result["findings"]) > 0
    assert result["error"] is None


def test_analyze_structure_api_error() -> None:
    """Node sets error and preserves empty findings when LLM raises."""
    mock_llm: Any = MagicMock()
    mock_llm.invoke.side_effect = Exception("API timeout")

    with patch("src.application.nodes.structure.get_llm", return_value=mock_llm):
        result = analyze_structure(_make_state())

    assert result["error"] is not None
    assert result["findings"] == []


def test_analyze_structure_appends_not_replaces() -> None:
    """New findings are appended to existing ones, not overwritten."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_VALID_RESPONSE)

    with patch("src.application.nodes.structure.get_llm", return_value=mock_llm):
        first_result = analyze_structure(_make_state())
        initial_count = len(first_result["findings"])
        assert initial_count > 0

        second_result = analyze_structure(first_result)

    assert len(second_result["findings"]) == initial_count * 2
