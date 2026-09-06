"""Use cases for uploading and listing thesis versions.

Extraction happens in-process: after the Phase 0 consolidation the parser is a
module in this service, so an upload is one function call rather than an HTTP
hop to a separate `parser` service.
"""

import uuid
from datetime import UTC, datetime
from uuid import UUID

import structlog

from src.document.extractor import extract
from src.mentoring.application.student_service import Caller, StudentService
from src.mentoring.domain.draft import ThesisDraft
from src.mentoring.infrastructure.models import ThesisDraftModel
from src.mentoring.infrastructure.repositories import ThesisDraftRepository

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
    )


class DraftService:
    """Turns an uploaded file into the next numbered version of a thesis."""

    def __init__(self, students: StudentService, drafts: ThesisDraftRepository) -> None:
        self._students = students
        self._drafts = drafts

    async def upload(
        self,
        caller: Caller,
        student_id: UUID,
        filename: str,
        data: bytes,
        content_type: str = "",
    ) -> ThesisDraft:
        """Extract an uploaded PDF/DOCX and store it as the next version.

        Raises ValueError for an unsupported or unreadable file, and
        StudentNotFoundError when the caller may not see the student.
        """
        student = await self._students.get(caller, student_id)
        document = extract(data, filename, content_type)

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
        )
        model = ThesisDraftModel(
            id=draft.id,
            student_id=draft.student_id,
            version_number=draft.version_number,
            filename=draft.filename,
            text=draft.text,
            pages=draft.pages,
            format=draft.format,
            uploaded_by=draft.uploaded_by,
            created_at=draft.created_at,
        )
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
