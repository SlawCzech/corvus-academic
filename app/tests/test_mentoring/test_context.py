"""Tests for what the agent is told about a student."""

import uuid
from datetime import UTC, datetime

from src.mentoring.application.context import assemble_propose_topic_context
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
