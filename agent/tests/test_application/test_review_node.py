"""Tests for the generate_review node — tone control and base behaviour."""

import json
from typing import Any, cast
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage

from src.application.nodes.review import generate_review
from src.application.state import AnalysisState, ThesisMetadataDict
from src.domain.analysis import Finding, FindingSeverity

_VALID_RESPONSE = json.dumps(
    {
        "scores": [
            {"criteria": "Struktura i spójność", "points": 8, "max_points": 10},
            {"criteria": "Metodologia i bibliografia", "points": 7, "max_points": 10},
            {"criteria": "Zgodność z wymogami", "points": 9, "max_points": 10},
            {"criteria": "Jakość merytoryczna", "points": 8, "max_points": 10},
        ],
        "review_text": "Praca spełnia wymagania stawiane pracom dyplomowym.",
        "recommendation": "Dopuścić do obrony",
    }
)

_CRITICAL_RESPONSE = json.dumps(
    {
        "scores": [
            {"criteria": "Struktura i spójność", "points": 3, "max_points": 10},
            {"criteria": "Metodologia i bibliografia", "points": 2, "max_points": 10},
            {"criteria": "Zgodność z wymogami", "points": 2, "max_points": 10},
            {"criteria": "Jakość merytoryczna", "points": 2, "max_points": 10},
        ],
        "review_text": "Praca wymaga istotnych poprawek przed dopuszczeniem do obrony.",
        "recommendation": "Zwrócić do poprawy",
    }
)


def _make_metadata(review_tone: str = "auto") -> ThesisMetadataDict:
    return cast(
        ThesisMetadataDict,
        {
            "author": "Anna Kowalska",
            "title": "Test Thesis",
            "year": 2024,
            "field_of_study": "Ekonomia",
            "thesis_type": "bachelor",
            "review_tone": review_tone,
        },
    )


def _make_state(
    with_critical: bool = False,
    with_major: bool = False,
    review_tone: str = "auto",
) -> AnalysisState:
    findings: list[Finding] = []
    if with_critical:
        findings.append(
            Finding(
                section="Metodologia",
                description="Brak projektu badawczego",
                severity=FindingSeverity.CRITICAL,
                suggestion="Dodaj rozdział z projektem badawczym.",
            )
        )
    if with_major:
        findings.append(
            Finding(
                section="Bibligrafia",
                description="Niewystarczające źródła",
                severity=FindingSeverity.MAJOR,
                suggestion="Rozbuduj bibliografię.",
            )
        )
    return cast(
        AnalysisState,
        {
            "evaluation_id": "550e8400-e29b-41d4-a716-446655440000",
            "metadata": _make_metadata(review_tone),
            "text": "Rozdział 1: Wprowadzenie. Rozdział 2: Przegląd literatury.",
            "guidelines": "Praca musi spełniać wymagania uczelniane.",
            "findings": findings,
            "scores": [],
            "review": None,
            "status": "analyzing",
            "error": None,
            "model": "qwen3:30b-a3b",
            "mode": "full",
            "review_tone": review_tone,
        },
    )


# ---------------------------------------------------------------------------
# Existing tests (updated for new field names)
# ---------------------------------------------------------------------------


def test_generate_review_happy_path() -> None:
    """Node produces a Review, non-empty scores, and sets status to 'analyzed'."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_VALID_RESPONSE)

    with patch("src.application.nodes.review.get_llm", return_value=mock_llm):
        result = generate_review(_make_state())

    assert result["review"] is not None
    assert len(result["scores"]) == 4
    assert result["status"] == "analyzed"
    assert result["error"] is None


def test_generate_review_rejected_when_critical_findings() -> None:
    """Node sets status to 'rejected' when findings include CRITICAL ones."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_CRITICAL_RESPONSE)

    with patch("src.application.nodes.review.get_llm", return_value=mock_llm):
        result = generate_review(_make_state(with_critical=True))

    assert result["status"] == "rejected"
    assert result["review"] is not None
    assert result["error"] is None


def test_generate_review_score_percentage() -> None:
    """Review total_percentage is computed correctly across scores."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_VALID_RESPONSE)

    with patch("src.application.nodes.review.get_llm", return_value=mock_llm):
        result = generate_review(_make_state())

    review = result["review"]
    assert review is not None
    # 8+7+9+8 = 32 out of 40 max → 80.0%
    assert review.total_percentage() == 80.0


def test_generate_review_recommendation_stored() -> None:
    """Review recommendation field matches what the LLM returned."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_VALID_RESPONSE)

    with patch("src.application.nodes.review.get_llm", return_value=mock_llm):
        result = generate_review(_make_state())

    assert result["review"] is not None
    assert result["review"].recommendation == "Dopuścić do obrony"


# ---------------------------------------------------------------------------
# Tone tests (from spec)
# ---------------------------------------------------------------------------


def test_auto_tone_prompt_contains_auto_instruction() -> None:
    """AUTO tone includes the AUTO tone instruction block in the system prompt."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_VALID_RESPONSE)

    captured_messages: list[Any] = []

    def capture_invoke(messages: list[Any]) -> AIMessage:
        captured_messages.extend(messages)
        return AIMessage(content=_VALID_RESPONSE)

    mock_llm.invoke.side_effect = capture_invoke

    with patch("src.application.nodes.review.get_llm", return_value=mock_llm):
        generate_review(_make_state(review_tone="auto"))

    system_content = str(captured_messages[0].content)
    assert "Tone instruction: AUTO" in system_content


def test_auto_tone_with_critical_finding_uses_negative_instruction() -> None:
    """AUTO tone with a CRITICAL finding includes NEGATIVE guidance in the prompt."""
    mock_llm = MagicMock()
    captured_messages: list[Any] = []

    def capture_invoke(messages: list[Any]) -> AIMessage:
        captured_messages.extend(messages)
        return AIMessage(content=_CRITICAL_RESPONSE)

    mock_llm.invoke.side_effect = capture_invoke

    with patch("src.application.nodes.review.get_llm", return_value=mock_llm):
        result = generate_review(_make_state(with_critical=True, review_tone="auto"))

    # Status must be rejected (domain rule) regardless of LLM recommendation
    assert result["status"] == "rejected"
    # AUTO instruction is present (not a hard-coded NEGATIVE instruction)
    system_content = str(captured_messages[0].content)
    assert "Tone instruction: AUTO" in system_content


def test_diplomatic_tone_prompt_tells_llm_to_skip_notable_strength() -> None:
    """DIPLOMATIC tone instruction explicitly forbids the notable strength section."""
    mock_llm = MagicMock()
    captured_messages: list[Any] = []

    def capture_invoke(messages: list[Any]) -> AIMessage:
        captured_messages.extend(messages)
        return AIMessage(content=_VALID_RESPONSE)

    mock_llm.invoke.side_effect = capture_invoke

    with patch("src.application.nodes.review.get_llm", return_value=mock_llm):
        generate_review(_make_state(review_tone="diplomatic"))

    system_content = str(captured_messages[0].content)
    assert "DO NOT include" in system_content
    assert "Tone instruction: DIPLOMATIC" in system_content


def test_negative_tone_prompt_forbids_positive_opening() -> None:
    """NEGATIVE tone instruction tells the LLM not to use the standard positive opening."""
    mock_llm = MagicMock()
    captured_messages: list[Any] = []

    def capture_invoke(messages: list[Any]) -> AIMessage:
        captured_messages.extend(messages)
        return AIMessage(content=_CRITICAL_RESPONSE)

    mock_llm.invoke.side_effect = capture_invoke

    with patch("src.application.nodes.review.get_llm", return_value=mock_llm):
        generate_review(_make_state(review_tone="negative"))

    system_content = str(captured_messages[0].content)
    assert "Tone instruction: NEGATIVE" in system_content
    assert "DO NOT use the standard positive opening" in system_content


def test_invalid_tone_falls_back_to_auto_without_crashing() -> None:
    """An unrecognised review_tone value is silently replaced by AUTO."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_VALID_RESPONSE)

    captured_messages: list[Any] = []

    def capture_invoke(messages: list[Any]) -> AIMessage:
        captured_messages.extend(messages)
        return AIMessage(content=_VALID_RESPONSE)

    mock_llm.invoke.side_effect = capture_invoke

    with patch("src.application.nodes.review.get_llm", return_value=mock_llm):
        result = generate_review(_make_state(review_tone="invalid_value"))

    # Node must not crash
    assert result["error"] is None
    assert result["review"] is not None
    # Fell back to AUTO
    system_content = str(captured_messages[0].content)
    assert "Tone instruction: AUTO" in system_content


def test_json_parse_error_sets_state_error() -> None:
    """Non-JSON LLM response causes state['error'] to be set (no exception propagated)."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="Sorry, I cannot comply.")

    with patch("src.application.nodes.review.get_llm", return_value=mock_llm):
        result = generate_review(_make_state())

    assert result["error"] is not None
    assert result["review"] is None
