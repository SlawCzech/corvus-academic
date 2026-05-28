"""Tests for the check_requirements node."""

from typing import Any, cast
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage

from src.application.nodes.requirements import check_requirements
from src.application.state import AnalysisState

_VALID_RESPONSE = (
    '[{"section": "Formatting", "description": "Page margins do not match guidelines",'
    ' "severity": "minor", "suggestion": "Set margins to 2.5cm as required."}]'
)

_EMPTY_RESPONSE = "[]"


def _make_state() -> AnalysisState:
    return cast(
        AnalysisState,
        {
            "evaluation_id": "550e8400-e29b-41d4-a716-446655440000",
            "metadata": {
                "author": "Jan Kowalski",
                "title": "Test Thesis",
                "year": 2024,
                "field_of_study": "Computer Science",
            },
            "text": "Chapter 1: Introduction. Chapter 2: Background.",
            "guidelines": "Thesis must have at least 5 chapters and proper margins.",
            "findings": [],
            "scores": [],
            "review": None,
            "status": "analyzing",
            "error": None,
        },
    )


def test_check_requirements_happy_path() -> None:
    """Node returns non-empty findings and no error on successful LLM call."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_VALID_RESPONSE)

    with patch("src.application.nodes.requirements.get_llm", return_value=mock_llm):
        result = check_requirements(_make_state())

    assert len(result["findings"]) > 0
    assert result["error"] is None


def test_check_requirements_no_violations() -> None:
    """Node returns empty findings when thesis fully conforms to guidelines."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_EMPTY_RESPONSE)

    with patch("src.application.nodes.requirements.get_llm", return_value=mock_llm):
        result = check_requirements(_make_state())

    assert result["findings"] == []
    assert result["error"] is None


def test_check_requirements_api_error() -> None:
    """Node sets error and preserves existing findings when LLM raises."""
    mock_llm: Any = MagicMock()
    mock_llm.invoke.side_effect = Exception("Timeout")

    with patch("src.application.nodes.requirements.get_llm", return_value=mock_llm):
        result = check_requirements(_make_state())

    assert result["error"] is not None
    assert result["findings"] == []


def test_check_requirements_appends_not_replaces() -> None:
    """New findings are appended to existing ones, not overwritten."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_VALID_RESPONSE)

    with patch("src.application.nodes.requirements.get_llm", return_value=mock_llm):
        first_result = check_requirements(_make_state())
        initial_count = len(first_result["findings"])
        assert initial_count > 0

        second_result = check_requirements(first_result)

    assert len(second_result["findings"]) == initial_count * 2
