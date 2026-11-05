"""Use cases for supervising students and recording meeting notes."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from src.mentoring.application.exceptions import (
    OneOffReviewError,
    StudentNotFoundError,
)
from src.mentoring.application.guidelines_port import GuidelineSource
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
    — every caller sees their own roster and nobody else's (ADR 0008) — so
    the two contexts stay decoupled.
    """

    user_id: UUID


def to_domain(model: StudentModel) -> Student:
    """Map a stored student row to the domain entity."""
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
        closed_at=model.closed_at,
        accepted_draft_id=model.accepted_draft_id,
        draft_accepted_at=model.draft_accepted_at,
        guideline_set_id=model.guideline_set_id,
        research_area=model.research_area,
        research_aim=model.research_aim,
        is_one_off=model.is_one_off,
    )


def _to_orm(student: Student) -> StudentModel:
    """The inverse of ``to_domain`` — a fresh row for a new student.

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
        closed_at=student.closed_at,
        accepted_draft_id=student.accepted_draft_id,
        draft_accepted_at=student.draft_accepted_at,
        guideline_set_id=student.guideline_set_id,
        research_area=student.research_area,
        research_aim=student.research_aim,
        is_one_off=student.is_one_off,
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
        guidelines: GuidelineSource | None = None,
    ) -> None:
        self._students = students
        self._notes = notes
        self._guidelines = guidelines

    # ---------- students ----------

    async def create(
        self,
        caller: Caller,
        full_name: str,
        field_of_study: str,
        thesis_type: ThesisType,
        index_number: str | None = None,
        created_at: datetime | None = None,
        research_area: str | None = None,
        research_aim: str | None = None,
        guideline_set_id: UUID | None = None,
    ) -> Student:
        """Add a student to the caller's roster.

        The domain entity is built first so its validation runs before
        anything reaches the database. ``created_at`` is for seeding a
        history; a student added through the API is dated now. A guideline
        set given here is checked like one picked later.
        """
        added = created_at or datetime.now(UTC)
        student = Student(
            id=uuid.uuid4(),
            promotor_id=caller.user_id,
            full_name=full_name,
            field_of_study=field_of_study,
            thesis_type=thesis_type,
            index_number=index_number,
            research_area=research_area,
            research_aim=research_aim,
            created_at=added,
            updated_at=added,
        )
        if guideline_set_id is not None:
            await self._check_guideline_set(student, guideline_set_id)
            student.guideline_set_id = guideline_set_id
        model = _to_orm(student)
        await self._students.save(model)
        return to_domain(model)

    async def add_one_off(
        self,
        caller: Caller,
        full_name: str,
        field_of_study: str,
        thesis_type: ThesisType,
        topic: str | None = None,
        research_area: str | None = None,
        research_aim: str | None = None,
        guideline_set_id: UUID | None = None,
    ) -> Student:
        """Write a one-off review's row, uncommitted: its thesis commits both."""
        student = Student.one_off(
            id=uuid.uuid4(),
            promotor_id=caller.user_id,
            full_name=full_name,
            field_of_study=field_of_study,
            thesis_type=thesis_type,
            research_area=research_area,
            research_aim=research_aim,
        )
        if topic and topic.strip():
            student.set_topic(topic, student.created_at)
        if guideline_set_id is not None:
            await self._check_guideline_set(student, guideline_set_id)
            student.guideline_set_id = guideline_set_id
        model = _to_orm(student)
        await self._students.add(model)
        return to_domain(model)

    async def discard_unsaved(self) -> None:
        """Drop a row `add_one_off` wrote, when its thesis cannot follow it."""
        await self._students.rollback()

    async def promote(self, caller: Caller, student_id: UUID) -> Student:
        """Turn a one-off review into a student on the caller's roster.

        Raises ValueError for someone who already is one.
        """
        model = await self._require_model(caller, student_id)
        student = to_domain(model)
        student.promote()
        model.is_one_off = student.is_one_off
        model.status = str(student.status)
        model.closed_at = student.closed_at
        await self._students.update(model)
        return to_domain(model)

    async def list_students(
        self,
        caller: Caller,
        status: StudentStatus | None = None,
        one_off: bool | None = None,
    ) -> list[Student]:
        """Return the caller's students.

        Left unset, `one_off` includes one-off reviews: whatever names an
        action needs them. The roster and the history each ask for their own.
        """
        models = await self._students.find_all(
            promotor_id=caller.user_id,
            status=str(status) if status is not None else None,
            one_off=one_off,
        )
        return [to_domain(m) for m in models]

    async def get(self, caller: Caller, student_id: UUID) -> Student:
        """Return one visible student. Raises StudentNotFoundError otherwise."""
        return to_domain(await self._require_model(caller, student_id))

    async def update(
        self,
        caller: Caller,
        student_id: UUID,
        current_topic: str | None = None,
        status: StudentStatus | None = None,
        guideline_set_id: UUID | None = None,
        set_guidelines: bool = False,
        full_name: str | None = None,
        field_of_study: str | None = None,
        thesis_type: ThesisType | None = None,
        index_number: str | None = None,
        set_index_number: bool = False,
        clear_topic: bool = False,
        topic_set_at: datetime | None = None,
        research_area: str | None = None,
        set_research_area: bool = False,
        research_aim: str | None = None,
        set_research_aim: bool = False,
    ) -> Student:
        """Edit the student: details, topic, lifecycle status, guideline set.

        Every field is optional; omitted ones are left untouched. Changes go
        through the domain entity so its rules hold — a topic is stamped with
        when it was set, a new thesis type drops a guideline set chosen for
        the old one. The ``set_*`` flags say a clearable field was given at
        all: with them, ``None`` clears it. ``clear_topic`` reopens the topic.
        ``topic_set_at`` dates the topic when seeding a history.

        Raises ValueError for a blank name, field, index number or topic, for
        a guideline set sent as null, and for one that does not exist, has
        nothing published, or is for another kind of thesis than the
        student's (after this change).
        """
        model = await self._require_model(caller, student_id)
        student = to_domain(model)

        student.update_details(full_name=full_name, field_of_study=field_of_study)
        if set_index_number:
            student.set_index_number(index_number)
        if set_research_area:
            student.set_research_area(research_area)
        if set_research_aim:
            student.set_research_aim(research_aim)
        if thesis_type is not None:
            student.change_thesis_type(thesis_type)
        if clear_topic:
            student.clear_topic()
        elif current_topic is not None:
            student.set_topic(current_topic, topic_set_at)
        # Checked against the thesis type as it is after this change.
        if set_guidelines:
            if guideline_set_id is None:
                # No built-in requirements to fall back on, ADR 0023.
                raise ValueError("A guideline set can be changed, not removed")
            await self._check_guideline_set(student, guideline_set_id)
            student.guideline_set_id = guideline_set_id
        if status is not None:
            student.change_status(status)

        model.full_name = student.full_name
        model.field_of_study = student.field_of_study
        model.index_number = student.index_number
        model.research_area = student.research_area
        model.research_aim = student.research_aim
        model.thesis_type = str(student.thesis_type)
        model.current_topic = student.current_topic
        model.current_topic_set_at = student.current_topic_set_at
        model.guideline_set_id = student.guideline_set_id
        model.status = str(student.status)
        model.closed_at = student.closed_at

        await self._students.update(model)
        return to_domain(model)

    async def _check_guideline_set(self, student: Student, set_id: UUID) -> None:
        if self._guidelines is None:  # pragma: no cover — wiring error
            raise RuntimeError("StudentService has no guideline source")
        thesis_type = await self._guidelines.thesis_type_of(set_id)
        if thesis_type is None:
            raise ValueError("Guideline set not found or has nothing published")
        if thesis_type != str(student.thesis_type):
            raise ValueError(
                f"Guideline set is for {thesis_type} theses, "
                f"the student writes a {student.thesis_type} one"
            )

    async def set_draft_acceptance(
        self,
        caller: Caller,
        student_id: UUID,
        draft_id: UUID | None,
        at: datetime | None = None,
    ) -> Student:
        """Mark a version as final, or clear the mark with ``draft_id=None``.

        ``at`` dates the acceptance when seeding a history; it is now otherwise.

        That the version belongs to this student is the caller's check to make
        — the draft service holds the drafts.
        """
        model = await self._require_model(caller, student_id)
        student = to_domain(model)
        if draft_id is None:
            student.clear_draft_acceptance()
        else:
            student.accept_draft(draft_id, at)
        model.accepted_draft_id = student.accepted_draft_id
        model.draft_accepted_at = student.draft_accepted_at
        await self._students.update(model)
        return to_domain(model)

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
        if student_model.is_one_off:
            raise OneOffReviewError("A one-off review has no meetings")
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
        if model.promotor_id != caller.user_id:
            raise StudentNotFoundError(str(student_id))
        return model
