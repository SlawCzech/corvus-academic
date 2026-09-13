"""Use cases for supervising students and recording meeting notes."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from src.mentoring.application.exceptions import StudentNotFoundError
from src.mentoring.domain.student import (
    MeetingNote,
    Student,
    StudentStatus,
    ThesisType,
)
from src.mentoring.infrastructure.orm import MeetingNoteModel, StudentModel
from src.mentoring.infrastructure.repositories import (
    MeetingNoteRepository,
    StudentRepository,
)


@dataclass(frozen=True)
class Caller:
    """The acting user, projected into the mentoring context.

    Deliberately not identity's ``User``: mentoring only needs who is acting
    and whether they may look past their own roster, so the permission lookup
    stays in the router and the two contexts stay decoupled.
    """

    user_id: UUID
    can_view_all: bool = False


def _to_domain(model: StudentModel) -> Student:
    return Student(
        id=model.id,
        promotor_id=model.promotor_id,
        full_name=model.full_name,
        field_of_study=model.field_of_study,
        thesis_type=ThesisType(model.thesis_type),
        index_number=model.index_number,
        current_topic=model.current_topic,
        current_topic_set_at=model.current_topic_set_at,
        status=StudentStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_orm(student: Student) -> StudentModel:
    """The inverse of ``_to_domain`` — a fresh row for a new student.

    Kept next to it for the same reason: the two are one fact read from
    opposite ends, and a field added to one that is forgotten in the other
    is exactly the bug this pairing makes easy to spot.
    """
    return StudentModel(
        id=student.id,
        promotor_id=student.promotor_id,
        full_name=student.full_name,
        index_number=student.index_number,
        field_of_study=student.field_of_study,
        thesis_type=str(student.thesis_type),
        current_topic=student.current_topic,
        current_topic_set_at=student.current_topic_set_at,
        status=str(student.status),
        created_at=student.created_at,
        updated_at=student.updated_at,
    )


def _note_to_domain(model: MeetingNoteModel) -> MeetingNote:
    return MeetingNote(
        id=model.id,
        student_id=model.student_id,
        promotor_id=model.promotor_id,
        occurred_at=model.occurred_at,
        content=model.content,
        source_action_id=model.source_action_id,
        created_at=model.created_at,
    )


def _note_to_orm(note: MeetingNote) -> MeetingNoteModel:
    """The inverse of ``_note_to_domain`` — a fresh row for a new note."""
    return MeetingNoteModel(
        id=note.id,
        student_id=note.student_id,
        promotor_id=note.promotor_id,
        occurred_at=note.occurred_at,
        content=note.content,
        source_action_id=note.source_action_id,
        created_at=note.created_at,
    )


class StudentService:
    """Orchestrates the student roster and its meeting notes."""

    def __init__(
        self,
        students: StudentRepository,
        notes: MeetingNoteRepository,
    ) -> None:
        self._students = students
        self._notes = notes

    # ---------- students ----------

    async def create(
        self,
        caller: Caller,
        full_name: str,
        field_of_study: str,
        thesis_type: ThesisType,
        index_number: str | None = None,
    ) -> Student:
        """Add a student to the caller's roster.

        The domain entity is built first so its validation runs before
        anything reaches the database.
        """
        student = Student(
            id=uuid.uuid4(),
            promotor_id=caller.user_id,
            full_name=full_name,
            field_of_study=field_of_study,
            thesis_type=thesis_type,
            index_number=index_number,
        )
        model = _to_orm(student)
        await self._students.save(model)
        return _to_domain(model)

    async def list_students(
        self,
        caller: Caller,
        status: StudentStatus | None = None,
    ) -> list[Student]:
        """Return the caller's students — or everyone's, for an admin."""
        promotor_filter = None if caller.can_view_all else caller.user_id
        models = await self._students.find_all(
            promotor_id=promotor_filter,
            status=str(status) if status is not None else None,
        )
        return [_to_domain(m) for m in models]

    async def get(self, caller: Caller, student_id: UUID) -> Student:
        """Return one visible student. Raises StudentNotFoundError otherwise."""
        return _to_domain(await self._require_model(caller, student_id))

    async def update(
        self,
        caller: Caller,
        student_id: UUID,
        current_topic: str | None = None,
        status: StudentStatus | None = None,
    ) -> Student:
        """Set the current topic and/or lifecycle status of a student.

        Both fields are optional; omitted ones are left untouched. Topic
        changes go through the domain entity so ``current_topic_set_at`` is
        always stamped with them.
        """
        model = await self._require_model(caller, student_id)
        student = _to_domain(model)

        if current_topic is not None:
            student.set_topic(current_topic)
            model.current_topic = student.current_topic
            model.current_topic_set_at = student.current_topic_set_at
        if status is not None:
            student.change_status(status)
            model.status = str(student.status)

        await self._students.update(model)
        return _to_domain(model)

    # ---------- meeting notes ----------

    async def add_meeting_note(
        self,
        caller: Caller,
        student_id: UUID,
        content: str,
        occurred_at: datetime | None = None,
        source_action_id: UUID | None = None,
    ) -> MeetingNote:
        """Record a meeting note against a visible student.

        ``promotor_id`` is the caller — whoever actually recorded the note,
        which for an admin acting on another roster is not the supervisor.
        """
        student_model = await self._require_model(caller, student_id)
        note = MeetingNote(
            id=uuid.uuid4(),
            student_id=student_model.id,
            promotor_id=caller.user_id,
            occurred_at=occurred_at or datetime.now(UTC),
            content=content,
            source_action_id=source_action_id,
        )
        model = _note_to_orm(note)
        await self._notes.save(model)
        return _note_to_domain(model)

    async def list_meeting_notes(
        self, caller: Caller, student_id: UUID
    ) -> list[MeetingNote]:
        """Return a visible student's meeting notes, most recent first."""
        student_model = await self._require_model(caller, student_id)
        models = await self._notes.find_by_student(student_model.id)
        return [_note_to_domain(m) for m in models]

    # ---------- internals ----------

    async def _require_model(self, caller: Caller, student_id: UUID) -> StudentModel:
        """Load a student the caller is allowed to see, or raise."""
        model = await self._students.find_by_id(student_id)
        if model is None:
            raise StudentNotFoundError(str(student_id))
        if not caller.can_view_all and model.promotor_id != caller.user_id:
            raise StudentNotFoundError(str(student_id))
        return model
