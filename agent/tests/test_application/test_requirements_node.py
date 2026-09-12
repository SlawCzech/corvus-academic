"""Tests for the check_requirements node."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage

from src.application.nodes.requirements import check_requirements
from src.application.state import ActionState
from src.domain.analysis import Finding, FindingSeverity
from tests.factories import make_state

_MINOR_RESPONSE = json.dumps(
    [
        {
            "section": "1.5 Formatowanie",
            "description": "Marginesy nie spełniają wymagań (3 cm zamiast 3,5 cm)",
            "severity": "minor",
            "suggestion": "Ustaw margines lewy na 3,5 cm.",
        }
    ]
)

_CRITICAL_RESPONSE = json.dumps(
    [
        {
            "section": "1.3 Wstęp",
            "description": "Brak celu pracy i pytań badawczych we wstępie",
            "severity": "critical",
            "suggestion": "Dodaj cel pracy oraz co najmniej jedno pytanie badawcze.",
        }
    ]
)

_EMPTY_RESPONSE = "[]"

_BACHELOR_GUIDELINES = (
    "## 4. Klasyfikacja uchybień\n"
    "### CRITICAL — Brak celu pracy\n"
    "### MAJOR — Niekompletny wstęp\n"
    "### MINOR — Błędy edytorskie\n"
)


def _make_state(
    extra_findings: list[Finding] | None = None,
    guidelines: str = _BACHELOR_GUIDELINES,
) -> ActionState:
    return make_state(
        findings=extra_findings or [],
        context={
            "text": "Rozdział 1: Wprowadzenie. Rozdział 2: Przegląd literatury.",
            "guidelines": guidelines,
            "metadata": {
                "author": "Anna Kowalska",
                "title": "Test Thesis",
                "year": 2024,
                "field_of_study": "Ekonomia",
                "thesis_type": "bachelor",
                "review_tone": "auto",
            },
            "review_tone": "auto",
        },
    )


# ---------------------------------------------------------------------------
# Spec tests
# ---------------------------------------------------------------------------


def test_node_appends_findings_to_existing_not_replaces() -> None:
    """New findings are appended to pre-existing findings, not overwritten."""
    existing = Finding(
        section="2.1 Bibligrafia",
        description="Za mało źródeł",
        severity=FindingSeverity.MAJOR,
        suggestion="Dodaj więcej źródeł.",
    )
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_MINOR_RESPONSE)

    with patch("src.application.nodes.requirements.get_llm", return_value=mock_llm):
        result = check_requirements(_make_state(extra_findings=[existing]))

    assert len(result["findings"]) == 2
    assert result["findings"][0] is existing


def test_node_parses_critical_severity_correctly() -> None:
    """Node correctly maps the 'critical' string to FindingSeverity.CRITICAL."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_CRITICAL_RESPONSE)

    with patch("src.application.nodes.requirements.get_llm", return_value=mock_llm):
        result = check_requirements(_make_state())

    assert len(result["findings"]) == 1
    assert result["findings"][0].severity == FindingSeverity.CRITICAL
    assert result["error"] is None


def test_node_returns_empty_findings_for_conforming_thesis() -> None:
    """Node returns empty findings list when model returns []."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_EMPTY_RESPONSE)

    with patch("src.application.nodes.requirements.get_llm", return_value=mock_llm):
        result = check_requirements(_make_state())

    assert result["findings"] == []
    assert result["error"] is None


def test_node_sets_error_when_model_returns_invalid_json() -> None:
    """Node sets state['error'] and does not crash when LLM returns non-JSON."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content="Przepraszam, nie mogę odpowiedzieć."
    )

    with patch("src.application.nodes.requirements.get_llm", return_value=mock_llm):
        result = check_requirements(_make_state())

    assert result["error"] is not None
    assert result["findings"] == []


def test_node_passes_guidelines_from_state_to_model_prompt() -> None:
    """Guidelines from state are included verbatim in the message sent to the LLM."""
    custom_guidelines = "UNIQUE_GUIDELINE_MARKER_XYZ"
    mock_llm = MagicMock()
    captured_messages: list[Any] = []

    def capture_invoke(messages: list[Any]) -> AIMessage:
        captured_messages.extend(messages)
        return AIMessage(content=_EMPTY_RESPONSE)

    mock_llm.invoke.side_effect = capture_invoke

    with patch("src.application.nodes.requirements.get_llm", return_value=mock_llm):
        check_requirements(_make_state(guidelines=custom_guidelines))

    human_content = str(captured_messages[1].content)
    assert custom_guidelines in human_content


def test_the_prompt_carries_the_map_of_what_the_excerpt_omits() -> None:
    """A chapter past the excerpt must reach the model as present, not absent.

    This is the regression that produced a review declaring four written
    chapters missing: the node saw a prefix of the thesis and judged the rest
    by its absence.
    """
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="[]")
    state = make_state(
        context={
            "text": "Wstęp. " * 5000,
            "guidelines": "The thesis must contain a methodology chapter.",
            "document_map": {
                "total_chars": 35000,
                "bibliography_entries": 41,
                "sections": [
                    {
                        "title": "Metodyka badań",
                        "canonical": "methodology",
                        "start": 30000,
                        "char_count": 5000,
                    }
                ],
            },
        }
    )

    with patch("src.application.nodes.requirements.get_llm", return_value=mock_llm):
        check_requirements(state)

    prompt = mock_llm.invoke.call_args[0][0][1].content
    assert "Metodyka badań" in prompt
    assert "Bibliography entries counted: 41" in prompt
    assert "NEVER report a section as missing" in prompt
