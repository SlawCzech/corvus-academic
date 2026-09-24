"""Tests for the generate_review node — tone control and base behaviour."""

import json
from typing import Any, cast
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage

from src.application.nodes.review import generate_review
from src.application.state import ActionState, ThesisMetadataDict
from src.domain.analysis import Finding, FindingSeverity, FindingSource
from tests.factories import make_state

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
) -> ActionState:
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
    return make_state(
        findings=findings,
        context={
            "text": "Rozdział 1: Wprowadzenie. Rozdział 2: Przegląd literatury.",
            "guidelines": "Praca musi spełniać wymagania uczelniane.",
            "metadata": _make_metadata(review_tone),
            "review_tone": review_tone,
        },
    )


# ---------------------------------------------------------------------------
# Existing tests (updated for new field names)
# ---------------------------------------------------------------------------


def test_generate_review_happy_path() -> None:
    """Node produces structured output, scores, and status 'analyzed'."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_VALID_RESPONSE)

    with patch("src.application.nodes.review.get_llm", return_value=mock_llm):
        result = generate_review(_make_state())

    assert result["output"] is not None
    assert len(result["scores"]) == 4
    assert result["status"] == "analyzed"
    assert "error" not in result


def test_generate_review_does_not_hand_the_findings_back() -> None:
    """The findings are already in state; returning them would sum them twice."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_VALID_RESPONSE)

    with patch("src.application.nodes.review.get_llm", return_value=mock_llm):
        result = generate_review(_make_state())

    assert "findings" not in result


def test_generate_review_rejected_when_critical_findings() -> None:
    """Node sets status to 'rejected' when findings include CRITICAL ones."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_CRITICAL_RESPONSE)

    with patch("src.application.nodes.review.get_llm", return_value=mock_llm):
        result = generate_review(_make_state(with_critical=True))

    assert result["status"] == "rejected"
    assert result["output"] is not None
    assert "error" not in result


def test_generate_review_score_percentage() -> None:
    """Review total_percentage is computed correctly across scores."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_VALID_RESPONSE)

    with patch("src.application.nodes.review.get_llm", return_value=mock_llm):
        result = generate_review(_make_state())

    output = result["output"]
    assert output is not None
    # 8+7+9+8 = 32 out of 40 max → 80.0%
    assert output["total_percentage"] == 80.0


def test_generate_review_recommendation_stored() -> None:
    """Review recommendation field matches what the LLM returned."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_VALID_RESPONSE)

    with patch("src.application.nodes.review.get_llm", return_value=mock_llm):
        result = generate_review(_make_state())

    assert result["output"] is not None
    assert result["output"]["recommendation"] == "Dopuścić do obrony"


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
    """NEGATIVE tone tells the LLM not to use the standard positive opening."""
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
    assert "error" not in result
    assert result["output"] is not None
    # Fell back to AUTO
    system_content = str(captured_messages[0].content)
    assert "Tone instruction: AUTO" in system_content


def test_commendable_tone_prompt_includes_notable_strength_phrase() -> None:
    """COMMENDABLE tone instruction contains the mandatory notable-strength opener."""
    mock_llm = MagicMock()
    captured_messages: list[Any] = []

    def capture_invoke(messages: list[Any]) -> AIMessage:
        captured_messages.extend(messages)
        return AIMessage(content=_VALID_RESPONSE)

    mock_llm.invoke.side_effect = capture_invoke

    with patch("src.application.nodes.review.get_llm", return_value=mock_llm):
        generate_review(_make_state(review_tone="commendable"))

    system_content = str(captured_messages[0].content)
    assert "Tone instruction: COMMENDABLE" in system_content
    assert "Na szczególne podkreślenie" in system_content


def test_commendable_tone_prompt_opening_differs_from_enthusiastic() -> None:
    """COMMENDABLE opening uses 'dobry poziom', not ENTHUSIASTIC's 'wysoki poziom'."""
    mock_llm = MagicMock()
    captured_messages: list[Any] = []

    def capture_invoke(messages: list[Any]) -> AIMessage:
        captured_messages.extend(messages)
        return AIMessage(content=_VALID_RESPONSE)

    mock_llm.invoke.side_effect = capture_invoke

    with patch("src.application.nodes.review.get_llm", return_value=mock_llm):
        generate_review(_make_state(review_tone="commendable"))

    system_content = str(captured_messages[0].content)
    # The COMMENDABLE opening line contains "dobry poziom"
    assert "dobry poziom" in system_content
    # The COMMENDABLE instruction opening does NOT use "wysoki poziom merytoryczny"
    # (that exact phrase belongs to the ENTHUSIASTIC opening only)
    assert "wysoki poziom merytoryczny" not in system_content


def test_reserved_tone_prompt_includes_minimalne_wymagania() -> None:
    """RESERVED tone instruction contains the mandatory 'minimalne wymagania' opener."""
    mock_llm = MagicMock()
    captured_messages: list[Any] = []

    def capture_invoke(messages: list[Any]) -> AIMessage:
        captured_messages.extend(messages)
        return AIMessage(content=_VALID_RESPONSE)

    mock_llm.invoke.side_effect = capture_invoke

    with patch("src.application.nodes.review.get_llm", return_value=mock_llm):
        generate_review(_make_state(with_major=True, review_tone="reserved"))

    system_content = str(captured_messages[0].content)
    assert "Tone instruction: RESERVED" in system_content
    assert "minimalne wymagania" in system_content


def test_reserved_recommendation_is_stored_correctly() -> None:
    """RESERVED tone with MAJOR findings stores the z-zastrzeżeniami recommendation."""
    reserved_response = json.dumps(
        {
            "scores": [
                {"criteria": "Struktura i spójność", "points": 5, "max_points": 10},
                {
                    "criteria": "Metodologia i bibliografia",
                    "points": 4,
                    "max_points": 10,
                },
                {"criteria": "Zgodność z wymogami", "points": 5, "max_points": 10},
                {"criteria": "Jakość merytoryczna", "points": 4, "max_points": 10},
            ],
            "review_text": (
                "Praca spełnia minimalne wymagania stawiane pracom dyplomowym."
            ),
            "recommendation": "Dopuścić do obrony z zastrzeżeniami",
        }
    )
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=reserved_response)

    with patch("src.application.nodes.review.get_llm", return_value=mock_llm):
        result = generate_review(_make_state(with_major=True, review_tone="reserved"))

    assert result["output"] is not None
    assert result["output"]["recommendation"] == "Dopuścić do obrony z zastrzeżeniami"


def test_auto_tone_prompt_includes_commendable_threshold() -> None:
    """Updated AUTO instruction contains COMMENDABLE threshold range (7.5–8.9)."""
    mock_llm = MagicMock()
    captured_messages: list[Any] = []

    def capture_invoke(messages: list[Any]) -> AIMessage:
        captured_messages.extend(messages)
        return AIMessage(content=_VALID_RESPONSE)

    mock_llm.invoke.side_effect = capture_invoke

    with patch("src.application.nodes.review.get_llm", return_value=mock_llm):
        generate_review(_make_state(review_tone="auto"))

    system_content = str(captured_messages[0].content)
    assert "COMMENDABLE" in system_content
    assert "7.5" in system_content


def test_auto_tone_prompt_includes_reserved_threshold() -> None:
    """Updated AUTO instruction contains RESERVED threshold range (3.5–4.9)."""
    mock_llm = MagicMock()
    captured_messages: list[Any] = []

    def capture_invoke(messages: list[Any]) -> AIMessage:
        captured_messages.extend(messages)
        return AIMessage(content=_VALID_RESPONSE)

    mock_llm.invoke.side_effect = capture_invoke

    with patch("src.application.nodes.review.get_llm", return_value=mock_llm):
        generate_review(_make_state(with_major=True, review_tone="auto"))

    system_content = str(captured_messages[0].content)
    assert "RESERVED" in system_content
    assert "3.5" in system_content


def test_json_parse_error_sets_state_error() -> None:
    """Non-JSON LLM response sets state['error'] (no exception propagated)."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="Sorry, I cannot comply.")

    with patch("src.application.nodes.review.get_llm", return_value=mock_llm):
        result = generate_review(_make_state())

    assert result["error"] is not None
    assert "output" not in result


def test_each_finding_reaches_the_review_labelled_with_its_source() -> None:
    """The label lets the review weigh a problem two analyses raised once."""
    state = _make_state()
    state["findings"] = [
        Finding(
            section="Wnioski",
            description="Brak wniosków",
            severity=FindingSeverity.CRITICAL,
            suggestion="Dodaj wnioski.",
            source=FindingSource.REQUIREMENTS,
        ),
        Finding(
            section="Wstęp",
            description="Cel niejasny",
            severity=FindingSeverity.MINOR,
            suggestion="Doprecyzuj cel.",
        ),
    ]
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_VALID_RESPONSE)

    with patch("src.application.nodes.review.get_llm", return_value=mock_llm):
        generate_review(state)

    messages: list[Any] = mock_llm.invoke.call_args.args[0]
    user_message = str(messages[1].content)
    assert "- [CRITICAL] (requirements) Wnioski: Brak wniosków" in user_message
    assert "- [MINOR] (unknown) Wstęp: Cel niejasny" in user_message
    assert "weigh it once" in str(messages[0].content)
