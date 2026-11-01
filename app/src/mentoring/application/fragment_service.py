"""Use cases for the parts of a thesis and the fragments handed in for them.

A fragment arrives by mail and the promoter enters it, so everything here is
the promoter's work: students have no accounts (ADR 0014).
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import structlog

from src.document.extractor import CANONICAL_CONTENT_TYPE, extract
from src.mentoring.application.exceptions import (
    FragmentNotFoundError,
    OneOffReviewError,
    PartConflictError,
    PartNotFoundError,
)
from src.mentoring.application.student_service import Caller, StudentService
from src.mentoring.domain.fragment import (
    FragmentVerdict,
    ThesisFragment,
    ThesisPart,
)
from src.mentoring.domain.student import Student
from src.mentoring.infrastructure.orm import ThesisFragmentModel, ThesisPartModel
from src.mentoring.infrastructure.repositories import (
    ThesisFragmentRepository,
    ThesisPartRepository,
)
from src.shared.files import FileStore, StoredFile

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# A chapter pasted from a mail is tens of thousands of characters at most.
MAX_PASTED_CHARS = 200_000

# `received_on` comes from the promoter's calendar, which may already be a day
# ahead of UTC.
_FUTURE_TOLERANCE = timedelta(days=1)


def part_to_domain(model: ThesisPartModel) -> ThesisPart:
    return ThesisPart(
        id=model.id,
        student_id=model.student_id,
        name=model.name,
        position=model.position,
        due_on=model.due_on,
        created_at=model.created_at,
    )


def fragment_to_domain(model: ThesisFragmentModel) -> ThesisFragment:
    return ThesisFragment(
        id=model.id,
        student_id=model.student_id,
        part_id=model.part_id,
        round_number=model.round_number,
        received_on=model.received_on,
        text=model.text,
        format=model.format,
        uploaded_by=model.uploaded_by,
        question=model.question,
        filename=model.filename,
        pages=model.pages,
        file_id=model.file_id,
        file_sha256=model.file_sha256,
        file_size=model.file_size,
        char_count=model.char_count,
        purged_at=model.purged_at,
        review_action_id=model.review_action_id,
        verdict=FragmentVerdict(model.verdict) if model.verdict else None,
        feedback=model.feedback,
        feedback_at=model.feedback_at,
        feedback_source_action_id=model.feedback_source_action_id,
        created_at=model.created_at,
    )


def fragment_to_orm(fragment: ThesisFragment) -> ThesisFragmentModel:
    return ThesisFragmentModel(
        id=fragment.id,
        student_id=fragment.student_id,
        part_id=fragment.part_id,
        round_number=fragment.round_number,
        received_on=fragment.received_on,
        question=fragment.question,
        text=fragment.text,
        char_count=fragment.char_count,
        pages=fragment.pages,
        format=fragment.format,
        filename=fragment.filename,
        uploaded_by=fragment.uploaded_by,
        file_id=fragment.file_id,
        file_sha256=fragment.file_sha256,
        file_size=fragment.file_size,
        created_at=fragment.created_at,
    )


async def purge_fragment(
    model: ThesisFragmentModel, files: FileStore, at: datetime
) -> ThesisFragment:
    """Drop one fragment's text and file; keep the row. Does not commit."""
    fragment = fragment_to_domain(model)
    file_id = fragment.file_id
    fragment.purge(at)
    model.text = fragment.text
    model.file_id = fragment.file_id
    model.purged_at = fragment.purged_at
    if file_id is not None:
        await files.delete(file_id)
    return fragment


@dataclass(frozen=True)
class FragmentUpload:
    """What was handed in: a file, or text pasted from a mail."""

    filename: str | None = None
    data: bytes | None = None
    content_type: str = ""
    text: str | None = None


@dataclass(frozen=True)
class _Content:
    """An upload read and checked, before anything is written."""

    text: str
    format: str
    pages: int = 0
    filename: str | None = None
    data: bytes | None = None


class FragmentService:
    """Parts of a thesis, and the fragments handed in for them."""

    def __init__(
        self,
        students: StudentService,
        parts: ThesisPartRepository,
        fragments: ThesisFragmentRepository,
        files: FileStore,
    ) -> None:
        self._students = students
        self._parts = parts
        self._fragments = fragments
        self._files = files

    # ---------- parts ----------

    async def add_part(
        self,
        caller: Caller,
        student_id: UUID,
        name: str,
        due_on: date | None = None,
    ) -> ThesisPart:
        """Add a part ahead of time, last in the order.

        Raises PartConflictError when the student already has one by that name.
        """
        student = await self._supervised(caller, student_id)
        part = ThesisPart(
            id=uuid.uuid4(), student_id=student.id, name=name, position=1, due_on=due_on
        )
        if await self._parts.find_by_name(student.id, part.name) is not None:
            raise PartConflictError(f"Part already exists: {part.name}")
        return part_to_domain(await self._insert_part(part))

    async def update_part(
        self,
        caller: Caller,
        student_id: UUID,
        part_id: UUID,
        name: str | None = None,
        position: int | None = None,
        due_on: date | None = None,
        change_due_on: bool = False,
    ) -> list[ThesisPart]:
        """Rename a part, move it, or change its deadline; return all parts.

        `due_on` of None is a real value, clearing the deadline, so taking it
        needs `change_due_on`. `position` counts from 1 and is clamped, so
        moving past either end puts the part there.

        Raises PartConflictError when another part has the new name.
        """
        student = await self._students.get(caller, student_id)
        model = await self._require_part(student, part_id)
        if name is not None:
            renamed = ThesisPart(
                id=model.id,
                student_id=model.student_id,
                name=name,
                position=model.position,
            ).name
            other = await self._parts.find_by_name(student.id, renamed)
            if other is not None and other.id != model.id:
                raise PartConflictError(f"Part already exists: {renamed}")
            model.name = renamed
        if change_due_on:
            model.due_on = due_on
        models = await self._parts.find_by_student(student.id)
        if position is not None:
            models = self._moved(models, model, position)
        await self._parts.commit()
        return [part_to_domain(m) for m in models]

    async def delete_part(
        self, caller: Caller, student_id: UUID, part_id: UUID
    ) -> None:
        """Remove a part nothing was handed in for.

        Raises PartConflictError when it has fragments: those are the record,
        and deleting a part must not be a way of losing them.
        """
        student = await self._students.get(caller, student_id)
        model = await self._require_part(student, part_id)
        if await self._fragments.count_by_part(model.id) > 0:
            raise PartConflictError(f"Part has fragments: {model.name}")
        await self._parts.delete(model)

    # ---------- fragments ----------

    async def upload(
        self,
        caller: Caller,
        student_id: UUID,
        part_name: str,
        upload: FragmentUpload,
        question: str | None = None,
        received_on: date | None = None,
        uploaded_at: datetime | None = None,
    ) -> ThesisFragment:
        """Record what the student handed in, as the next round of the part.

        The part is found by name, whatever its case, or created. A deadline on
        it is met by this fragment and goes. An accepted version stays
        accepted: only a whole version can replace a whole version.

        `uploaded_at` is for seeding a history, as on a draft.

        Raises ValueError for unusable input, and StudentNotFoundError when the
        caller may not see the student.
        """
        student = await self._supervised(caller, student_id)
        now = uploaded_at or datetime.now(UTC)
        received = received_on or now.date()
        if received > now.date() + _FUTURE_TOLERANCE:
            raise ValueError("received_on must not be in the future")

        content = self._read(upload)

        name = ThesisPart(
            id=uuid.uuid4(), student_id=student.id, name=part_name, position=1
        ).name
        part = await self._parts.find_by_name(student.id, name)
        if part is None:
            part = await self._insert_part(
                ThesisPart(
                    id=uuid.uuid4(), student_id=student.id, name=name, position=1
                )
            )
        part.due_on = None

        # After the part, whose insert commits. Written in the same commit as
        # the fragment: the store flushes, the repository commits, so a file
        # never exists without its fragment.
        stored = (
            await self._files.put(
                content.filename or "",
                CANONICAL_CONTENT_TYPE[content.format],
                content.data,
            )
            if content.data is not None
            else None
        )
        round_number = await self._fragments.next_round_number(part.id)
        fragment = ThesisFragment(
            id=uuid.uuid4(),
            student_id=student.id,
            part_id=part.id,
            round_number=round_number,
            received_on=received,
            text=content.text,
            format=content.format,
            uploaded_by=caller.user_id,
            question=(question or "").strip() or None,
            filename=content.filename,
            pages=content.pages,
            file_id=stored.id if stored else None,
            file_sha256=stored.sha256 if stored else None,
            file_size=stored.size if stored else None,
            created_at=now,
        )
        model = fragment_to_orm(fragment)
        await self._fragments.save(model)
        logger.info(
            "fragment_uploaded",
            student_id=str(student.id),
            part_id=str(part.id),
            round=round_number,
            format=fragment.format,
            chars=fragment.char_count,
        )
        return fragment_to_domain(model)

    async def download(
        self, caller: Caller, student_id: UUID, fragment_id: UUID
    ) -> tuple[StoredFile, bytes]:
        """Return the original upload of one fragment.

        Raises FragmentNotFoundError when it is not this student's or has no
        file — pasted text never had one, a purged fragment lost it.
        """
        student = await self._students.get(caller, student_id)
        model = await self._require_fragment(student, fragment_id)
        if model.file_id is None:
            raise FragmentNotFoundError(str(fragment_id))
        found = await self._files.get(model.file_id)
        if found is None:
            raise FragmentNotFoundError(str(fragment_id))
        return found

    async def answer(
        self,
        caller: Caller,
        student_id: UUID,
        fragment_id: UUID,
        verdict: FragmentVerdict,
        feedback: str | None = None,
        source_action_id: UUID | None = None,
        next_due_on: date | None = None,
        at: datetime | None = None,
    ) -> ThesisFragment:
        """Save what the promoter told the student. Saving again corrects it.

        `source_action_id` says the text started from that run's draft. It must
        be the run the fragment points at: a draft nobody was shown cannot have
        been used. `next_due_on` sets the deadline of this fragment's part.
        `at` is for seeding a history.

        Raises ValueError for a run that is not this fragment's.
        """
        student = await self._students.get(caller, student_id)
        model = await self._require_fragment(student, fragment_id)
        if source_action_id is not None and source_action_id != model.review_action_id:
            raise ValueError("That run is not this fragment's latest")

        fragment = fragment_to_domain(model)
        fragment.record_feedback(
            verdict, feedback, at or datetime.now(UTC), source_action_id
        )
        model.verdict = str(fragment.verdict)
        model.feedback = fragment.feedback
        model.feedback_at = fragment.feedback_at
        model.feedback_source_action_id = fragment.feedback_source_action_id
        if next_due_on is not None:
            part = await self._parts.find_by_id(model.part_id)
            if part is not None:
                part.due_on = next_due_on
        await self._fragments.update(model)
        logger.info(
            "fragment_feedback_recorded",
            student_id=str(student.id),
            fragment_id=str(model.id),
            verdict=str(verdict),
            ai_drafted=source_action_id is not None,
        )
        return fragment_to_domain(model)

    # ---------- internals ----------

    @staticmethod
    def _read(upload: FragmentUpload) -> _Content:
        """Extract or check the upload; raises ValueError when it is unusable."""
        if (upload.data is None) == (upload.text is None):
            raise ValueError("Send either a file or text, not both or neither")
        if upload.data is not None:
            filename = upload.filename or ""
            document = extract(upload.data, filename, upload.content_type)
            return _Content(
                text=document.text,
                format=document.format,
                pages=document.pages,
                filename=filename,
                data=upload.data,
            )
        text = upload.text or ""
        if len(text) > MAX_PASTED_CHARS:
            raise ValueError(f"Text longer than {MAX_PASTED_CHARS} characters")
        if not text.strip():
            raise ValueError("fragment text must not be empty")
        return _Content(text=text, format="text")

    async def _supervised(self, caller: Caller, student_id: UUID) -> Student:
        """The student, unless it is a one-off review: those have no parts."""
        student = await self._students.get(caller, student_id)
        if student.is_one_off:
            raise OneOffReviewError("A one-off review has no parts or fragments")
        return student

    async def _insert_part(self, part: ThesisPart) -> ThesisPartModel:
        model = ThesisPartModel(
            id=part.id,
            student_id=part.student_id,
            name=part.name,
            position=await self._parts.next_position(part.student_id),
            due_on=part.due_on,
            created_at=part.created_at,
        )
        await self._parts.save(model)
        return model

    @staticmethod
    def _moved(
        models: list[ThesisPartModel], model: ThesisPartModel, position: int
    ) -> list[ThesisPartModel]:
        """Put one part at `position`, renumbering the rest from 1."""
        others = [m for m in models if m.id != model.id]
        index = min(max(position, 1), len(models)) - 1
        ordered = [*others[:index], model, *others[index:]]
        for number, part in enumerate(ordered, start=1):
            part.position = number
        return ordered

    async def _require_part(self, student: Student, part_id: UUID) -> ThesisPartModel:
        model = await self._parts.find_by_id(part_id)
        if model is None or model.student_id != student.id:
            raise PartNotFoundError(str(part_id))
        return model

    async def _require_fragment(
        self, student: Student, fragment_id: UUID
    ) -> ThesisFragmentModel:
        model = await self._fragments.find_by_id(fragment_id)
        if model is None or model.student_id != student.id:
            raise FragmentNotFoundError(str(fragment_id))
        return model
