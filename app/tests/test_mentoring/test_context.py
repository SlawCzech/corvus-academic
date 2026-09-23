"""Tests for what the agent is told about a student."""

import uuid
from datetime import UTC, datetime

from src.mentoring.application.context import (
    assemble_evaluate_methodology_context,
    assemble_generate_review_context,
    assemble_propose_topic_context,
)
from src.mentoring.domain.draft import ThesisDraft
from src.mentoring.domain.student import MeetingNote, Student, ThesisType


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
    context = assemble_generate_review_context(_student(), _draft(_LONG_THESIS))

    document_map = context["document_map"]
    assert document_map["total_chars"] == len(_LONG_THESIS)
    assert "methodology" in [s["canonical"] for s in document_map["sections"]]


def test_the_map_locates_a_chapter_past_any_excerpt() -> None:
    context = assemble_generate_review_context(_student(), _draft(_LONG_THESIS))

    methodology = next(
        s
        for s in context["document_map"]["sections"]
        if s["canonical"] == "methodology"
    )
    assert methodology["start"] > 10000
    assert methodology["char_count"] > 0


def test_sources_are_counted_in_app_not_guessed_by_the_model() -> None:
    context = assemble_generate_review_context(_student(), _draft(_LONG_THESIS))

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


def test_without_a_rubric_the_key_is_absent_so_the_agent_loads_its_own() -> None:
    """`agent` falls back exactly when `guidelines` is not in the context."""
    context = assemble_generate_review_context(_student(), _draft(_LONG_THESIS))

    assert "guidelines" not in context
