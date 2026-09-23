"""The retention sweep: purge every version whose time has come.

The rules are `domain/retention.py`; this only finds the students that could
have something due, asks the policy, and applies the answer. Idempotent — a
purged version is never due again — so running it twice, or from two replicas
at once, does no harm.
"""

from datetime import datetime

import structlog

from src.mentoring.application.draft_service import purge_draft
from src.mentoring.application.draft_service import to_domain as draft_to_domain
from src.mentoring.application.student_service import to_domain as student_to_domain
from src.mentoring.domain.retention import RetentionPolicy
from src.mentoring.infrastructure.repositories import (
    StudentRepository,
    ThesisDraftRepository,
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
    ) -> None:
        self._students = students
        self._drafts = drafts
        self._files = files
        self._policy = policy or RetentionPolicy()

    async def sweep(self, now: datetime) -> int:
        """Purge what is due at ``now``; return how many versions were purged."""
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
            if due:
                await self._drafts.commit()
                purged += len(due)
        logger.info("retention_sweep_complete", purged=purged)
        return purged
