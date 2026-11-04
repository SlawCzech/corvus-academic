"""Tests for the generate_review node — tone control and base behaviour."""

import json
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from src.application.nodes.review import (
    advice_in,
    allowed_recommendations,
    generate_review,
)
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
        "review_text": "Praca nie spełnia wymagań stawianych pracom dyplomowym.",
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
    # No findings, so no criterion goes below 8: the 7 is raised.
    # 8+8+9+8 = 33 out of 40 max → 82.5%
    assert output["total_percentage"] == 82.5


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

    def capture_invoke(messages: list[Any], **_: Any) -> AIMessage:  # noqa: ANN401
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

    def capture_invoke(messages: list[Any], **_: Any) -> AIMessage:  # noqa: ANN401
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

    def capture_invoke(messages: list[Any], **_: Any) -> AIMessage:  # noqa: ANN401
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

    def capture_invoke(messages: list[Any], **_: Any) -> AIMessage:  # noqa: ANN401
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

    def capture_invoke(messages: list[Any], **_: Any) -> AIMessage:  # noqa: ANN401
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

    def capture_invoke(messages: list[Any], **_: Any) -> AIMessage:  # noqa: ANN401
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

    def capture_invoke(messages: list[Any], **_: Any) -> AIMessage:  # noqa: ANN401
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

    def capture_invoke(messages: list[Any], **_: Any) -> AIMessage:  # noqa: ANN401
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

    def capture_invoke(messages: list[Any], **_: Any) -> AIMessage:  # noqa: ANN401
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

    def capture_invoke(messages: list[Any], **_: Any) -> AIMessage:  # noqa: ANN401
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


# ---------------------------------------------------------------------------
# The recommendation follows from the findings
# ---------------------------------------------------------------------------


def test_a_critical_finding_leaves_only_return_for_revision() -> None:
    from src.application.nodes.review import allowed_recommendations

    critical = _make_state(with_critical=True)["findings"]
    major = _make_state(with_major=True)["findings"]

    assert allowed_recommendations(critical) == ("Zwrócić do poprawy",)
    assert allowed_recommendations(major) == (
        "Dopuścić do obrony",
        "Dopuścić do obrony z zastrzeżeniami",
    )
    assert allowed_recommendations(critical, "en") == ("Returned for revision",)


def test_a_recommendation_the_findings_rule_out_gets_repaired() -> None:
    """From an eval run: a sound thesis, no CRITICAL finding, "returned"."""
    wrong = json.loads(_VALID_RESPONSE) | {"recommendation": "Zwrócić do poprawy"}
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [
        AIMessage(content=json.dumps(wrong)),
        AIMessage(content=_VALID_RESPONSE),
    ]

    with patch("src.application.nodes.review.get_llm", return_value=mock_llm):
        result = generate_review(_make_state(with_major=True))

    assert result["output"] is not None
    assert result["output"]["recommendation"] == "Dopuścić do obrony"
    repair = mock_llm.invoke.call_args_list[1].args[0][-1].content
    assert "recommendation" in repair
    first_prompt = mock_llm.invoke.call_args_list[0].args[0][1].content
    assert "Allowed recommendation (decided by the findings): Dopuścić" in first_prompt


def test_scores_outside_what_the_findings_allow_are_moved_into_range() -> None:
    """One MAJOR finding in methodology: 7–8 there, 8–10 where nothing is major."""
    low = json.dumps(
        {
            "scores": [
                {"criteria": "Struktura i spójność", "points": 6, "max_points": 10},
                {"criteria": "Metodologia i bibliografia", "points": 4},
                {"criteria": "Zgodność z wymogami", "points": 5, "max_points": 10},
                {"criteria": "Jakość merytoryczna", "points": 10, "max_points": 10},
            ],
            "review_text": "Praca spełnia wymagania stawiane pracom dyplomowym.",
            "recommendation": "Dopuścić do obrony z zastrzeżeniami",
        }
    )
    state = make_state(
        findings=[
            Finding(
                section="Metodologia",
                description="Dobór próby nieopisany",
                severity=FindingSeverity.MAJOR,
                suggestion="Opisz dobór próby.",
                source=FindingSource.METHODOLOGY,
            )
        ],
        context={"text": "Rozdział 1.", "metadata": _make_metadata()},
    )
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=low)

    with patch("src.application.nodes.review.get_llm", return_value=mock_llm):
        result = generate_review(state)

    assert [s.points for s in result["scores"]] == [8, 7, 8, 8]
    user_message = mock_llm.invoke.call_args.args[0][1].content
    assert "8–10, 7–8, 8–10, 7–8" in user_message


def _reply_saying(text: str) -> str:
    return json.dumps({**json.loads(_VALID_RESPONSE), "review_text": text})


_ADVISING_RESPONSE = _reply_saying(
    "Wykaz literatury wymaga ujednolicenia. Zalecam odniesienie się do tego "
    "podczas obrony."
)
_STATING_RESPONSE = _reply_saying("Wykaz literatury jest niejednolity.")


def _replying(*replies: str) -> MagicMock:
    llm = MagicMock()
    llm.invoke.side_effect = [AIMessage(content=reply) for reply in replies]
    return llm


def _summary_of(llm: MagicMock) -> str:
    with patch("src.application.nodes.review.get_llm", return_value=llm):
        result = generate_review(_make_state())
    output = cast(dict[str, Any], result["output"])
    return str(output["summary"])


def test_the_prompt_says_the_thesis_is_finished() -> None:
    llm = _replying(_VALID_RESPONSE)

    _summary_of(llm)

    system = str(llm.invoke.call_args_list[0].args[0][0].content)
    assert "will not be changed" in system
    assert "Nothing about the defence" in system


def test_no_tone_asks_for_corrections() -> None:
    for tone in (
        "auto",
        "enthusiastic",
        "commendable",
        "positive",
        "diplomatic",
        "reserved",
        "negative",
    ):
        llm = _replying(_CRITICAL_RESPONSE)
        with patch("src.application.nodes.review.get_llm", return_value=llm):
            generate_review(_make_state(review_tone=tone))

        system = str(llm.invoke.call_args_list[0].args[0][0].content)
        assert "must be corrected" not in system, tone
        assert "wymaga istotnych poprawek" not in system, tone


def test_a_review_that_gives_advice_is_rewritten_once() -> None:
    llm = _replying(_ADVISING_RESPONSE, _STATING_RESPONSE)

    summary = _summary_of(llm)

    assert summary == "Wykaz literatury jest niejednolity."
    assert llm.invoke.call_count == 2
    rewrite = str(llm.invoke.call_args_list[1].args[0][-1].content)
    assert "Zalecam" in rewrite
    assert "podczas obrony" in rewrite


def test_a_clean_review_costs_no_second_call() -> None:
    llm = _replying(_VALID_RESPONSE)

    _summary_of(llm)

    assert llm.invoke.call_count == 1


def test_a_stubborn_review_is_kept_rather_than_lost() -> None:
    llm = _replying(_ADVISING_RESPONSE, _ADVISING_RESPONSE)

    summary = _summary_of(llm)

    assert "Zalecam" in summary
    assert llm.invoke.call_count == 2


@pytest.mark.parametrize(
    "text",
    [
        "Zalecam odniesienie się do tych kwestii.",
        "Wstęp powinien zawierać charakterystykę literatury.",
        "Wykaz literatury wymaga ujednolicenia.",
        "Należy uzupełnić bibliografię.",
        "Praca wymaga istotnych poprawek.",
        "Kwestię tę warto poruszyć podczas obrony.",
        "Praca nadaje się do poprawy.",
        "Dopuszczam pracę do obrony.",
        "This should be addressed during the defense.",
    ],
)
def test_advice_is_recognised(text: str) -> None:
    assert advice_in(text)


@pytest.mark.parametrize(
    "text",
    [
        "Baza źródłowa jest wąska.",
        "Wykaz literatury jest niejednolity.",
        "Autor powinien był szerzej uzasadnić dobór próby.",
        "Należy podkreślić trafny dobór metod.",
        "Praca dotyczy wydatków na obronę narodową.",
        "Wymagania formalne zostały spełnione.",
    ],
)
def test_a_judgement_is_not_taken_for_advice(text: str) -> None:
    assert advice_in(text) == []


def _trial_state(*findings: Finding) -> ActionState:
    state = _make_state()
    return cast(
        ActionState,
        {**state, "action_type": "trial_review", "findings": list(findings)},
    )


def _trial_reply(recommendation: str, text: str) -> str:
    return json.dumps(
        {
            **json.loads(_VALID_RESPONSE),
            "review_text": text,
            "recommendation": recommendation,
        }
    )


def _finding(severity: FindingSeverity) -> Finding:
    return Finding(
        section="Metodologia",
        description="Opis",
        severity=severity,
        suggestion="Popraw.",
    )


def test_a_trial_review_keeps_its_advice_and_has_its_own_prompt() -> None:
    llm = _replying(
        _trial_reply(
            "Gotowa do złożenia",
            "Wykaz literatury wymaga ujednolicenia przed złożeniem.",
        )
    )

    with patch("src.application.nodes.review.get_llm", return_value=llm):
        result = generate_review(_trial_state())

    system = str(llm.invoke.call_args_list[0].args[0][0].content)
    assert "not submitted yet" in system
    assert "will not be changed" not in system
    assert "Tone instruction" not in system
    assert llm.invoke.call_count == 1
    output = cast(dict[str, Any], result["output"])
    assert "wymaga ujednolicenia" in str(output["summary"])
    assert output["recommendation"] == "Gotowa do złożenia"


def test_a_final_label_is_no_recommendation_for_a_trial_review() -> None:
    llm = _replying(
        _VALID_RESPONSE, _trial_reply("Gotowa do złożenia", "Tekst próbnej recenzji.")
    )

    with patch("src.application.nodes.review.get_llm", return_value=llm):
        result = generate_review(_trial_state())

    assert cast(dict[str, Any], result["output"])["recommendation"] == (
        "Gotowa do złożenia"
    )


@pytest.mark.parametrize(
    ("severity", "expected"),
    [
        (
            FindingSeverity.MINOR,
            ("Gotowa do złożenia", "Gotowa do złożenia po poprawkach"),
        ),
        (FindingSeverity.MAJOR, ("Gotowa do złożenia po poprawkach",)),
        (FindingSeverity.CRITICAL, ("Wymaga istotnych poprawek",)),
    ],
)
def test_the_findings_decide_a_trial_recommendation(
    severity: FindingSeverity, expected: tuple[str, ...]
) -> None:
    assert allowed_recommendations([_finding(severity)], trial=True) == expected
