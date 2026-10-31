"""The retention sweep: purge every version and fragment whose time has come.

The rules are `domain/retention.py`; this only finds the students that could
have something due, asks the policy, and applies the answer. Idempotent — a
purged version is never due again — so running it twice, or from two replicas
at once, does no harm.
"""

from datetime import datetime

import structlog

from src.mentoring.application.draft_service import purge_draft
from src.mentoring.application.draft_service import to_domain as draft_to_domain
from src.mentoring.application.fragment_service import (
    fragment_to_domain,
    purge_fragment,
)
from src.mentoring.application.student_service import to_domain as student_to_domain
from src.mentoring.domain.retention import RetentionPolicy
from src.mentoring.domain.student import Student
from src.mentoring.infrastructure.repositories import (
    StudentRepository,
    ThesisDraftRepository,
    ThesisFragmentRepository,
)
from src.shared.files import FileStore

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class RetentionService:
    """Applies the retention policy across every student."""

    def __init__(
        self,
        students: StudentRepository,
        drafts: ThesisDraftRepository,
        files: FileStore,
        policy: RetentionPolicy | None = None,
        fragments: ThesisFragmentRepository | None = None,
    ) -> None:
        self._students = students
        self._drafts = drafts
        self._files = files
        self._fragments = fragments
        self._policy = policy or RetentionPolicy()

    async def sweep(self, now: datetime) -> int:
        """Purge what is due at ``now``; return how many items were purged."""
        purged = 0
        for student_model in await self._students.find_retention_candidates():
            student = student_to_domain(student_model)
            models = {m.id: m for m in await self._drafts.find_by_student(student.id)}
            due = self._policy.drafts_to_purge(
                student, [draft_to_domain(m) for m in models.values()], now
            )
            for draft in due:
                await purge_draft(models[draft.id], self._files, now)
                logger.info(
                    "draft_purged",
                    student_id=str(student.id),
                    version=draft.version_number,
                    reason="retention",
                )
            purged_fragments = await self._purge_fragments(student, now)
            if due or purged_fragments:
                await self._drafts.commit()
                purged += len(due) + purged_fragments
        logger.info("retention_sweep_complete", purged=purged)
        return purged

    async def _purge_fragments(self, student: Student, now: datetime) -> int:
        """Purge a student's fragments that are due. Does not commit."""
        if self._fragments is None:
            return 0
        models = {m.id: m for m in await self._fragments.find_by_student(student.id)}
        due = self._policy.fragments_to_purge(
            student, [fragment_to_domain(m) for m in models.values()], now
        )
        for fragment in due:
            await purge_fragment(models[fragment.id], self._files, now)
            logger.info(
                "fragment_purged",
                student_id=str(student.id),
                fragment_id=str(fragment.id),
                reason="retention",
            )
        return len(due)
