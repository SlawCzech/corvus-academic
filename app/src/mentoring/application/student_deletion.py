"""Deleting a student outright — the immediate form of the retention purge.

Retention (ADR 0006) empties a version and keeps its row, so the history
still says which version each result was about. Deleting the student leaves
no history to keep: every row goes, and so does every file.

The files need their own step. A version or a fragment points at its file,
not the other way round, so no cascade from the student ever reaches
`draft_files`; left to the database, deleting a student would strand their
work there for good.
"""

from uuid import UUID

import structlog

from src.mentoring.application.agent_client import AgentClient
from src.mentoring.application.student_service import Caller, StudentService
from src.mentoring.infrastructure.repositories import (
    StudentRepository,
    ThesisDraftRepository,
    ThesisFragmentRepository,
)
from src.shared.files import FileStore

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class StudentDeletionService:
    """Deletes a student with everything recorded about them."""

    def __init__(
        self,
        students: StudentService,
        student_rows: StudentRepository,
        drafts: ThesisDraftRepository,
        files: FileStore,
        agent: AgentClient,
        fragments: ThesisFragmentRepository | None = None,
    ) -> None:
        self._students = students
        self._student_rows = student_rows
        self._drafts = drafts
        self._files = files
        self._agent = agent
        self._fragments = fragments

    async def delete(self, caller: Caller, student_id: UUID, token: str) -> None:
        """Delete the student, their notes, work, files and AI results.

        The agent's copies of the results go first — reviews and proposed
        topics are the student's data too. If the agent cannot be reached,
        AgentUnavailableError is raised and nothing here is touched; trying
        again is safe, the agent's side is idempotent. Everything in `app`
        then goes in one commit.

        Raises StudentNotFoundError when the caller may not see the student.
        """
        student = await self._students.get(caller, student_id)
        await self._agent.delete_student_actions(student.id, token)

        drafts = await self._drafts.find_by_student(student.id)
        for draft in drafts:
            if draft.file_id is not None:
                await self._files.delete(draft.file_id)
        fragments = (
            await self._fragments.find_by_student(student.id)
            if self._fragments is not None
            else []
        )
        for fragment in fragments:
            if fragment.file_id is not None:
                await self._files.delete(fragment.file_id)
        await self._student_rows.delete(student.id)
        logger.info(
            "student_deleted",
            student_id=str(student.id),
            promotor_id=str(caller.user_id),
            versions=len(drafts),
            fragments=len(fragments),
        )
