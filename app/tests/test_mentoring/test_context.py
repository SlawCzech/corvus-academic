"""Tests for what the agent is told about a student."""

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from src.mentoring.application.context import (
    assemble_check_progress_context,
    assemble_evaluate_methodology_context,
    assemble_generate_review_context,
    assemble_propose_topic_context,
    notes_between_versions,
)
from src.mentoring.application.exceptions import MissingContextError
from src.mentoring.domain.draft import ThesisDraft
from src.mentoring.domain.student import MeetingNote, Student, ThesisType

_RUBRIC = {
    "elements": "Wstęp z celem.",
    "formal": "Objętość sugerowana.",
    "merit": "Logiczny tok wywodu.",
    "severity": "CRITICAL: brak wstępu.",
}


def _student(current_topic: str | None = None) -> Student:
    return Student(
        id=uuid.uuid4(),
        promotor_id=uuid.uuid4(),
        full_name="Jan Kowalski",
        field_of_study="Ekonomia",
        thesis_type=ThesisType.BACHELOR,
        current_topic=current_topic,
    )


def _note(content: str) -> MeetingNote:
    return MeetingNote(
        id=uuid.uuid4(),
        student_id=uuid.uuid4(),
        promotor_id=uuid.uuid4(),
        occurred_at=datetime(2026, 3, 1, tzinfo=UTC),
        content=content,
    )


def test_context_describes_the_student() -> None:
    context = assemble_propose_topic_context(_student(), detail="coś ilościowego")

    assert context["field_of_study"] == "Ekonomia"
    assert context["thesis_type"] == "bachelor"
    assert context["detail"] == "coś ilościowego"
    assert context["current_topic"] is None


def test_existing_topic_is_sent_so_the_model_can_refine_it() -> None:
    context = assemble_propose_topic_context(_student("Instytucje a wzrost"))
    assert context["current_topic"] == "Instytucje a wzrost"


def test_only_the_last_few_notes_are_sent() -> None:
    """Context is the state of play, not the student's whole file."""
    notes = [_note(f"Notatka {i}") for i in range(6)]

    context = assemble_propose_topic_context(_student(), notes)

    assert context["recent_notes"] == ["Notatka 0", "Notatka 1", "Notatka 2"]


def test_context_without_notes_is_still_valid() -> None:
    context = assemble_propose_topic_context(_student())
    assert context["recent_notes"] == []


def _draft(text: str) -> ThesisDraft:
    return ThesisDraft(
        id=uuid.uuid4(),
        student_id=uuid.uuid4(),
        version_number=1,
        filename="praca.pdf",
        text=text,
        pages=40,
        format="pdf",
        uploaded_by=uuid.uuid4(),
    )


_V1_AT = datetime(2026, 3, 1, 12, tzinfo=UTC)
_V2_AT = datetime(2026, 4, 1, 12, tzinfo=UTC)


def _versions() -> list[ThesisDraft]:
    """The two newest versions, newest first, as the repository returns them."""
    previous = replace(_draft("Wersja pierwsza"), created_at=_V1_AT)
    current = replace(_draft("Wersja druga"), version_number=2, created_at=_V2_AT)
    return [current, previous]


def _note_at(content: str, occurred_at: datetime) -> MeetingNote:
    return replace(_note(content), occurred_at=occurred_at)


def test_only_notes_between_the_two_versions_count() -> None:
    notes = [
        _note_at("po", _V2_AT + timedelta(minutes=1)),
        _note_at("między", _V1_AT + timedelta(days=7)),
        _note_at("przed", _V1_AT - timedelta(minutes=1)),
    ]

    picked = notes_between_versions(notes, _versions())

    assert [n.content for n in picked] == ["między"]


def test_notes_between_versions_run_from_the_oldest() -> None:
    """Later notes stand over earlier ones, so the model reads them in order."""
    notes = [
        _note_at("druga", _V1_AT + timedelta(days=14)),
        _note_at("pierwsza", _V1_AT + timedelta(days=7)),
    ]

    picked = notes_between_versions(notes, _versions())

    assert [n.content for n in picked] == ["pierwsza", "druga"]


def test_every_note_between_the_versions_is_kept() -> None:
    """The window bounds them: a cap would drop the oldest request."""
    notes = [_note_at(str(i), _V1_AT + timedelta(days=i)) for i in range(1, 8)]

    assert len(notes_between_versions(notes, _versions())) == 7


def test_one_version_has_no_window_for_notes() -> None:
    assert notes_between_versions([_note("coś")], [_draft("Jedyna")]) == []


def test_progress_context_carries_the_notes_it_is_given() -> None:
    context = assemble_check_progress_context(
        _student(), _versions(), [_note("Uzasadnić dobór próby")], "skup się na próbie"
    )

    assert context["meeting_notes"] == ["Uzasadnić dobór próby"]
    assert context["detail"] == "skup się na próbie"


def test_progress_context_without_notes_has_none_to_show() -> None:
    assert (
        assemble_check_progress_context(_student(), _versions())["meeting_notes"] == []
    )


_LONG_THESIS = "\n".join(
    [
        "Wstęp",
        "Wprowadzenie do tematu. " * 500,
        "Metodyka badań",
        "Zastosowano podejście ilościowe. " * 500,
        "Bibliografia:",
        "1. Adamczyk, J. (2004). Internet na usługach marketingu. Rzeszów: OW.",
    ]
)


def test_review_context_maps_the_document_the_agent_will_only_see_part_of() -> None:
    """The agent reads an excerpt; without this map it judges the rest absent."""
    context = assemble_generate_review_context(
        _student(), _draft(_LONG_THESIS), guidelines=_RUBRIC
    )

    document_map = context["document_map"]
    assert document_map["total_chars"] == len(_LONG_THESIS)
    assert "methodology" in [s["canonical"] for s in document_map["sections"]]


def test_the_map_locates_a_chapter_past_any_excerpt() -> None:
    context = assemble_generate_review_context(
        _student(), _draft(_LONG_THESIS), guidelines=_RUBRIC
    )

    methodology = next(
        s
        for s in context["document_map"]["sections"]
        if s["canonical"] == "methodology"
    )
    assert methodology["start"] > 10000
    assert methodology["char_count"] > 0


def test_sources_are_counted_in_app_not_guessed_by_the_model() -> None:
    context = assemble_generate_review_context(
        _student(), _draft(_LONG_THESIS), guidelines=_RUBRIC
    )

    assert context["document_map"]["bibliography_entries"] == 1


def test_a_chosen_guideline_rubric_travels_in_the_context() -> None:
    review = assemble_generate_review_context(
        _student(), _draft(_LONG_THESIS), guidelines="## Wymogi UE Katowice"
    )
    methodology = assemble_evaluate_methodology_context(
        _student(), _draft(_LONG_THESIS), guidelines="## Wymogi UE Katowice"
    )

    assert review["guidelines"] == "## Wymogi UE Katowice"
    assert methodology["guidelines"] == "## Wymogi UE Katowice"


def test_thresholds_travel_with_the_review_and_stay_out_of_methodology() -> None:
    """Only the requirements node reads them, and only a review runs it."""
    review = assemble_generate_review_context(
        _student(),
        _draft(_LONG_THESIS),
        guidelines=_RUBRIC,
        thresholds={"min_sources": 25},
    )
    methodology = assemble_evaluate_methodology_context(
        _student(), _draft(_LONG_THESIS), guidelines=_RUBRIC
    )

    assert review["thresholds"] == {"min_sources": 25}
    assert "thresholds" not in methodology


def test_without_thresholds_the_key_is_absent() -> None:
    context = assemble_generate_review_context(
        _student(), _draft(_LONG_THESIS), guidelines=_RUBRIC
    )

    assert "thresholds" not in context


def test_without_a_rubric_the_review_and_methodology_are_refused() -> None:
    """No built-in requirements to fall back on, ADR 0023."""
    with pytest.raises(MissingContextError, match="guidelines"):
        assemble_generate_review_context(_student(), _draft(_LONG_THESIS))
    with pytest.raises(MissingContextError, match="guidelines"):
        assemble_evaluate_methodology_context(_student(), _draft(_LONG_THESIS))


def test_a_rubric_by_section_travels_as_sections() -> None:
    context = assemble_generate_review_context(
        _student(), _draft(_LONG_THESIS), guidelines=_RUBRIC
    )

    assert context["guidelines"] == _RUBRIC


def test_a_full_review_carries_what_was_agreed_with_the_student() -> None:
    student = _student("Instytucje a wzrost")
    student.research_area = "ekonomia instytucjonalna"
    student.research_aim = "Cel: zbadać X."

    context = assemble_generate_review_context(
        student, _draft("Tekst pracy."), guidelines=_RUBRIC
    )

    assert context["research_area"] == "ekonomia instytucjonalna"
    assert context["research_aim"] == "Cel: zbadać X."


def test_methodology_hears_the_field_as_well_as_the_topic() -> None:
    student = _student("Instytucje a wzrost")

    context = assemble_evaluate_methodology_context(
        student, _draft("Tekst pracy."), guidelines=_RUBRIC
    )

    assert context["current_topic"] == "Instytucje a wzrost"
    assert context["field_of_study"] == student.field_of_study
    assert context["research_aim"] is None


def test_the_map_counts_the_pages_of_a_pdf_only() -> None:
    """A Word file's page count is what the last program to save it wrote."""
    pdf = assemble_generate_review_context(
        _student(), _draft("Tekst pracy."), guidelines=_RUBRIC
    )
    docx = assemble_generate_review_context(
        _student(),
        replace(_draft("Tekst pracy."), format="docx", filename="praca.docx"),
        guidelines=_RUBRIC,
    )

    assert pdf["document_map"]["pages"] == 40
    assert docx["document_map"]["pages"] is None
