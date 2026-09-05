"""Unit tests for the mentoring domain entities — no database, no framework."""

import uuid
from datetime import UTC, datetime

import pytest

from src.mentoring.domain.student import (
    MeetingNote,
    Student,
    StudentStatus,
    ThesisType,
)


def _student(**overrides: object) -> Student:
    kwargs: dict[str, object] = {
        "id": uuid.uuid4(),
        "promotor_id": uuid.uuid4(),
        "full_name": "Jan Kowalski",
        "field_of_study": "Ekonomia",
        "thesis_type": ThesisType.BACHELOR,
    }
    kwargs.update(overrides)
    return Student(**kwargs)  # type: ignore[arg-type]


# ---------- Student validation ----------


def test_student_strips_whitespace() -> None:
    student = _student(full_name="  Jan Kowalski  ", field_of_study=" Ekonomia ")
    assert student.full_name == "Jan Kowalski"
    assert student.field_of_study == "Ekonomia"


def test_student_rejects_blank_full_name() -> None:
    with pytest.raises(ValueError, match="full_name"):
        _student(full_name="   ")


def test_student_rejects_blank_field_of_study() -> None:
    with pytest.raises(ValueError, match="field_of_study"):
        _student(field_of_study="")


def test_student_rejects_blank_index_number_when_given() -> None:
    with pytest.raises(ValueError, match="index_number"):
        _student(index_number="  ")


def test_student_allows_missing_index_number() -> None:
    assert _student().index_number is None


def test_student_defaults_to_active() -> None:
    assert _student().status is StudentStatus.ACTIVE


# ---------- topic ----------


def test_new_student_has_no_topic() -> None:
    student = _student()
    assert student.has_topic is False
    assert student.current_topic_set_at is None


def test_set_topic_stamps_time() -> None:
    student = _student()
    student.set_topic("  Wpływ instytucji na wzrost  ")
    assert student.current_topic == "Wpływ instytucji na wzrost"
    assert student.has_topic is True
    assert student.current_topic_set_at is not None


def test_set_topic_accepts_explicit_time() -> None:
    student = _student()
    moment = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
    student.set_topic("Temat", at=moment)
    assert student.current_topic_set_at == moment


def test_set_topic_rejects_blank() -> None:
    student = _student()
    with pytest.raises(ValueError, match="topic"):
        student.set_topic("   ")


# ---------- ownership and status ----------


def test_is_supervised_by() -> None:
    promotor_id = uuid.uuid4()
    student = _student(promotor_id=promotor_id)
    assert student.is_supervised_by(promotor_id) is True
    assert student.is_supervised_by(uuid.uuid4()) is False


def test_change_status() -> None:
    student = _student()
    student.change_status(StudentStatus.GRADUATED)
    assert student.status is StudentStatus.GRADUATED


# ---------- MeetingNote ----------


def _note(**overrides: object) -> MeetingNote:
    kwargs: dict[str, object] = {
        "id": uuid.uuid4(),
        "student_id": uuid.uuid4(),
        "promotor_id": uuid.uuid4(),
        "occurred_at": datetime(2026, 3, 1, 10, 0, tzinfo=UTC),
        "content": "Omówiliśmy zakres rozdziału teoretycznego.",
    }
    kwargs.update(overrides)
    return MeetingNote(**kwargs)  # type: ignore[arg-type]


def test_meeting_note_rejects_blank_content() -> None:
    with pytest.raises(ValueError, match="content"):
        _note(content="\n  ")


def test_handwritten_note_is_not_ai_drafted() -> None:
    assert _note().is_ai_drafted is False


def test_note_from_accepted_action_is_ai_drafted() -> None:
    assert _note(source_action_id=uuid.uuid4()).is_ai_drafted is True
