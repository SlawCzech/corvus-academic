"""What the promoter does with a fragment once it is in.

Apart from `FragmentService` because both of these reach for `ActionService`,
which itself reads fragments.
"""

from datetime import UTC, date, datetime
from uuid import UUID

import structlog

from src.mentoring.application.action_service import ActionService
from src.mentoring.application.exceptions import FragmentNotFoundError
from src.mentoring.application.fragment_service import fragment_to_domain
from src.mentoring.application.student_service import Caller, StudentService
from src.mentoring.domain.fragment import FragmentVerdict, ThesisFragment
from src.mentoring.domain.student import Student
from src.mentoring.infrastructure.orm import ThesisFragmentModel
from src.mentoring.infrastructure.repositories import (
    ThesisFragmentRepository,
    ThesisPartRepository,
)
from src.shared.files import FileStore

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class FragmentFeedbackService:
    """Records the promoter's feedback, and takes back a mistaken upload."""

    def __init__(
        self,
        students: StudentService,
        parts: ThesisPartRepository,
        fragments: ThesisFragmentRepository,
        files: FileStore,
        actions: ActionService,
    ) -> None:
        self._students = students
        self._parts = parts
        self._fragments = fragments
        self._files = files
        self._actions = actions

    async def record(
        self,
        caller: Caller,
        student_id: UUID,
        fragment_id: UUID,
        verdict: FragmentVerdict,
        feedback: str | None = None,
        source_action_id: UUID | None = None,
        next_due_on: date | None = None,
    ) -> ThesisFragment:
        """Save what the promoter told the student. Saving again corrects it.

        `source_action_id` says the text started from that run's draft, which
        marks the run accepted. It must be the run the fragment points at: a
        draft nobody was shown cannot have been used. `next_due_on` sets the
        deadline of this fragment's part.

        Raises ValueError for a run that is not this fragment's.
        """
        student = await self._students.get(caller, student_id)
        model = await self._require_fragment(student, fragment_id)
        if source_action_id is not None and source_action_id != model.review_action_id:
            raise ValueError("That run is not this fragment's latest")

        fragment = fragment_to_domain(model)
        fragment.record_feedback(
            verdict, feedback, datetime.now(UTC), source_action_id
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
        if source_action_id is not None:
            await self._actions.mark_used(caller, student.id, source_action_id)
        logger.info(
            "fragment_feedback_recorded",
            student_id=str(student.id),
            fragment_id=str(model.id),
            verdict=str(verdict),
            ai_drafted=source_action_id is not None,
        )
        return fragment_to_domain(model)

    async def delete(
        self, caller: Caller, student_id: UUID, fragment_id: UUID, token: str
    ) -> None:
        """Take back a mistaken upload: row, file, and every run on it.

        The runs go first, each through `ActionService.delete`, so the agent's
        copies go too. If the agent cannot be reached, AgentUnavailableError
        is raised and the fragment stays; trying again is safe (ADR 0009).
        Its round number is free again for what replaces it.
        """
        student = await self._students.get(caller, student_id)
        model = await self._require_fragment(student, fragment_id)
        for run_id in await self._actions.runs_on_fragment(student.id, model.id):
            await self._actions.delete(caller, student.id, run_id, token)
        if model.file_id is not None:
            await self._files.delete(model.file_id)
        await self._fragments.delete(model)
        logger.info(
            "fragment_deleted", student_id=str(student.id), fragment_id=str(model.id)
        )

    async def _require_fragment(
        self, student: Student, fragment_id: UUID
    ) -> ThesisFragmentModel:
        model = await self._fragments.find_by_id(fragment_id)
        if model is None or model.student_id != student.id:
            raise FragmentNotFoundError(str(fragment_id))
        return model
