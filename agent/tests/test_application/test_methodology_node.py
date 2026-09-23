"""Tests for the analyze_methodology node."""

from typing import Any
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage

from src.application.nodes.methodology import analyze_methodology
from src.application.state import ActionState
from src.domain.analysis import Finding, FindingSeverity
from tests.factories import make_state

_VALID_RESPONSE = (
    '[{"section": "Methodology", "description": "Research design not clearly stated",'
    ' "severity": "major", "suggestion": "Add a research design section."}]'
)


def _make_state() -> ActionState:
    return make_state(
        context={
            "text": "Chapter 3: Methodology. We used a qualitative approach.",
            "guidelines": "The thesis must describe the research method in detail.",
            "metadata": {
                "author": "Jan Kowalski",
                "title": "Test Thesis",
                "year": 2024,
                "field_of_study": "Computer Science",
            },
        }
    )


def test_analyze_methodology_happy_path() -> None:
    """Node returns non-empty findings and no error on successful LLM call."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_VALID_RESPONSE)

    with patch("src.application.nodes.methodology.get_llm", return_value=mock_llm):
        result = analyze_methodology(_make_state())

    assert len(result["findings"]) > 0
    assert "node_errors" not in result


def test_analyze_methodology_api_error() -> None:
    """Node sets error and preserves empty findings when LLM raises."""
    mock_llm: Any = MagicMock()
    mock_llm.invoke.side_effect = Exception("Connection refused")

    with patch("src.application.nodes.methodology.get_llm", return_value=mock_llm):
        result = analyze_methodology(_make_state())

    # Reported for the review to carry, not as the action's own error.
    assert result == {"node_errors": ["methodology: Connection refused"]}


def test_analyze_methodology_returns_only_its_own_findings() -> None:
    """Earlier findings stay out of the update — the state's reducer sums them.

    Handing the whole list back would double it: the branches run in
    parallel and LangGraph adds each update to what is already there.
    """
    earlier = Finding(
        section="Wstęp",
        description="earlier",
        severity=FindingSeverity.MINOR,
        suggestion="-",
    )
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_VALID_RESPONSE)

    with patch("src.application.nodes.methodology.get_llm", return_value=mock_llm):
        state = _make_state()
        state["findings"] = [earlier]
        result = analyze_methodology(state)

    assert earlier not in result["findings"]
    assert len(result["findings"]) == 1
