"""Use cases for uploading and listing thesis versions.

Extraction happens in-process: after the Phase 0 consolidation the parser is a
module in this service, so an upload is one function call rather than an HTTP
hop to a separate `parser` service.
"""

import uuid
from datetime import UTC, datetime
from uuid import UUID

import structlog

from src.document.extractor import CANONICAL_CONTENT_TYPE, extract
from src.mentoring.application.exceptions import DraftNotFoundError
from src.mentoring.application.student_service import Caller, StudentService
from src.mentoring.domain.draft import ThesisDraft
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
    )


class DraftService:
    """Turns an uploaded file into the next numbered version of a thesis."""

    def __init__(
        self,
        students: StudentService,
        drafts: ThesisDraftRepository,
        files: FileStore,
    ) -> None:
        self._students = students
        self._drafts = drafts
        self._files = files

    async def upload(
        self,
        caller: Caller,
        student_id: UUID,
        filename: str,
        data: bytes,
        content_type: str = "",
    ) -> ThesisDraft:
        """Extract an uploaded PDF/DOCX; store file and text as the next version.

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
            created_at=datetime.now(UTC),
            file_id=stored.id,
            file_sha256=stored.sha256,
            file_size=stored.size,
        )
        model = to_orm(draft)
        await self._drafts.save(model)
        logger.info(
            "draft_uploaded",
            student_id=str(student.id),
            version=version,
            format=draft.format,
            chars=draft.char_count,
        )
        return to_domain(model)

    async def list_drafts(self, caller: Caller, student_id: UUID) -> list[ThesisDraft]:
        """Return a student's versions, newest first."""
        student = await self._students.get(caller, student_id)
        models = await self._drafts.find_by_student(student.id)
        return [to_domain(m) for m in models]

    async def download(
        self, caller: Caller, student_id: UUID, draft_id: UUID
    ) -> tuple[StoredFile, bytes]:
        """Return the original upload of one version.

        Raises StudentNotFoundError when the caller may not see the student, and
        DraftNotFoundError when the version is not this student's or has no file.
        """
        student = await self._students.get(caller, student_id)
        model = await self._drafts.find_by_id(draft_id)
        if model is None or model.student_id != student.id or model.file_id is None:
            raise DraftNotFoundError(str(draft_id))
        found = await self._files.get(model.file_id)
        if found is None:
            raise DraftNotFoundError(str(draft_id))
        return found
