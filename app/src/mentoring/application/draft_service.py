"""Use cases for thesis versions: upload, listing, download, acceptance, purge.

Extraction happens in-process: after the Phase 0 consolidation the parser is a
module in this service, so an upload is one function call rather than an HTTP
hop to a separate `parser` service.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import structlog

from src.document.extractor import CANONICAL_CONTENT_TYPE, extract
from src.mentoring.application.exceptions import DraftNotFoundError
from src.mentoring.application.student_service import Caller, StudentService
from src.mentoring.domain.draft import ThesisDraft
from src.mentoring.domain.retention import RetentionPolicy
from src.mentoring.domain.student import Student
from src.mentoring.infrastructure.orm import ThesisDraftModel
from src.mentoring.infrastructure.repositories import ThesisDraftRepository
from src.shared.files import FileStore, StoredFile

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def to_domain(model: ThesisDraftModel) -> ThesisDraft:
    """Map a stored draft row to the domain entity."""
    return ThesisDraft(
        id=model.id,
        student_id=model.student_id,
        version_number=model.version_number,
        filename=model.filename,
        text=model.text,
        pages=model.pages,
        format=model.format,
        uploaded_by=model.uploaded_by,
        created_at=model.created_at,
        file_id=model.file_id,
        file_sha256=model.file_sha256,
        file_size=model.file_size,
        char_count=model.char_count,
        purged_at=model.purged_at,
    )


def to_orm(draft: ThesisDraft) -> ThesisDraftModel:
    """The inverse of ``to_domain`` — a fresh row for a new version."""
    return ThesisDraftModel(
        id=draft.id,
        student_id=draft.student_id,
        version_number=draft.version_number,
        filename=draft.filename,
        text=draft.text,
        pages=draft.pages,
        format=draft.format,
        uploaded_by=draft.uploaded_by,
        created_at=draft.created_at,
        file_id=draft.file_id,
        file_sha256=draft.file_sha256,
        file_size=draft.file_size,
        char_count=draft.char_count,
        purged_at=draft.purged_at,
    )


async def purge_draft(
    model: ThesisDraftModel, files: FileStore, at: datetime
) -> ThesisDraft:
    """Drop one version's text and file; keep the row. Does not commit.

    Shared by the promoter's "delete this version" and the retention sweep, so
    both leave exactly the same trace behind.
    """
    draft = to_domain(model)
    file_id = draft.file_id
    draft.purge(at)
    model.text = draft.text
    model.file_id = draft.file_id
    model.purged_at = draft.purged_at
    if file_id is not None:
        await files.delete(file_id)
    return draft


@dataclass(frozen=True)
class DraftView:
    """A version as the promoter sees it: the draft plus what the student
    record says about it."""

    draft: ThesisDraft
    is_accepted: bool
    purge_due_at: datetime | None


class DraftService:
    """Turns uploads into numbered versions, and manages what happens to them."""

    def __init__(
        self,
        students: StudentService,
        drafts: ThesisDraftRepository,
        files: FileStore,
        policy: RetentionPolicy | None = None,
    ) -> None:
        self._students = students
        self._drafts = drafts
        self._files = files
        self._policy = policy or RetentionPolicy()

    async def upload(
        self,
        caller: Caller,
        student_id: UUID,
        filename: str,
        data: bytes,
        content_type: str = "",
        uploaded_at: datetime | None = None,
    ) -> DraftView:
        """Extract an uploaded PDF/DOCX; store file and text as the next version.

        A new version supersedes an accepted one: the thesis came back, so no
        version is final any more. ``uploaded_at`` is for seeding a history;
        the HTTP upload never passes it, so a real version is dated now.

        Raises ValueError for an unsupported or unreadable file, and
        StudentNotFoundError when the caller may not see the student.
        """
        student = await self._students.get(caller, student_id)
        document = extract(data, filename, content_type)

        # Written in the same commit as the draft row below: the store flushes,
        # the repository commits, so a file never exists without its draft.
        stored = await self._files.put(
            filename, CANONICAL_CONTENT_TYPE[document.format], data
        )
        version = await self._drafts.next_version_number(student.id)
        draft = ThesisDraft(
            id=uuid.uuid4(),
            student_id=student.id,
            version_number=version,
            filename=filename,
            text=document.text,
            pages=document.pages,
            format=document.format,
            uploaded_by=caller.user_id,
            created_at=uploaded_at or datetime.now(UTC),
            file_id=stored.id,
            file_sha256=stored.sha256,
            file_size=stored.size,
        )
        model = to_orm(draft)
        await self._drafts.save(model)
        if student.accepted_draft_id is not None:
            student = await self._students.set_draft_acceptance(
                caller, student.id, None
            )
        logger.info(
            "draft_uploaded",
            student_id=str(student.id),
            version=version,
            format=draft.format,
            chars=draft.char_count,
        )
        return self._view(student, to_domain(model))

    async def list_drafts(self, caller: Caller, student_id: UUID) -> list[DraftView]:
        """Return a student's versions, newest first."""
        student = await self._students.get(caller, student_id)
        models = await self._drafts.find_by_student(student.id)
        return [self._view(student, to_domain(m)) for m in models]

    async def download(
        self, caller: Caller, student_id: UUID, draft_id: UUID
    ) -> tuple[StoredFile, bytes]:
        """Return the original upload of one version.

        Raises StudentNotFoundError when the caller may not see the student, and
        DraftNotFoundError when the version is not this student's or has no file.
        """
        student = await self._students.get(caller, student_id)
        model = await self._require_draft(student, draft_id)
        if model.file_id is None:
            raise DraftNotFoundError(str(draft_id))
        found = await self._files.get(model.file_id)
        if found is None:
            raise DraftNotFoundError(str(draft_id))
        return found

    async def accept(
        self,
        caller: Caller,
        student_id: UUID,
        draft_id: UUID,
        at: datetime | None = None,
    ) -> list[DraftView]:
        """Mark one version as final; the others start their purge countdown.

        ``at`` dates the acceptance when seeding a history; it is now otherwise.

        Raises DraftNotFoundError for a version that is not this student's or
        has already been purged — there is nothing left to accept.
        """
        student = await self._students.get(caller, student_id)
        model = await self._require_draft(student, draft_id)
        if model.purged_at is not None:
            raise DraftNotFoundError(str(draft_id))
        await self._students.set_draft_acceptance(caller, student.id, model.id, at)
        logger.info(
            "draft_accepted", student_id=str(student.id), version=model.version_number
        )
        return await self.list_drafts(caller, student_id)

    async def clear_acceptance(
        self, caller: Caller, student_id: UUID, draft_id: UUID
    ) -> list[DraftView]:
        """Undo the acceptance of this version; a no-op if it is not the accepted one.

        Undone before the grace period ends, nothing is purged.
        """
        student = await self._students.get(caller, student_id)
        if student.accepted_draft_id == draft_id:
            await self._students.set_draft_acceptance(caller, student.id, None)
            logger.info("draft_acceptance_cleared", student_id=str(student.id))
        return await self.list_drafts(caller, student_id)

    async def purge(
        self, caller: Caller, student_id: UUID, draft_id: UUID
    ) -> list[DraftView]:
        """Delete one version's text and file now, at the promoter's request.

        The row stays, as it does under retention. Purging the accepted version
        also clears the acceptance — there is no final version left to keep.
        """
        student = await self._students.get(caller, student_id)
        model = await self._require_draft(student, draft_id)
        if model.purged_at is None:
            await purge_draft(model, self._files, datetime.now(UTC))
            await self._drafts.update(model)
            logger.info(
                "draft_purged",
                student_id=str(student.id),
                version=model.version_number,
                reason="promoter",
            )
        if student.accepted_draft_id == draft_id:
            await self._students.set_draft_acceptance(caller, student.id, None)
        return await self.list_drafts(caller, student_id)

    # ---------- internals ----------

    async def _require_draft(
        self, student: Student, draft_id: UUID
    ) -> ThesisDraftModel:
        model = await self._drafts.find_by_id(draft_id)
        if model is None or model.student_id != student.id:
            raise DraftNotFoundError(str(draft_id))
        return model

    def _view(self, student: Student, draft: ThesisDraft) -> DraftView:
        return DraftView(
            draft=draft,
            is_accepted=student.accepted_draft_id == draft.id,
            purge_due_at=self._policy.purge_due_at(student, draft),
        )
