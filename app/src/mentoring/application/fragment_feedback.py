"""What the promoter does with a fragment once it is in.

Apart from `FragmentService` because both of these reach for `ActionService`,
which itself reads fragments.
"""

from datetime import date
from uuid import UUID

import structlog

from src.mentoring.application.action_service import ActionService
from src.mentoring.application.exceptions import FragmentNotFoundError
from src.mentoring.application.fragment_service import FragmentService
from src.mentoring.application.student_service import Caller, StudentService
from src.mentoring.domain.fragment import FragmentVerdict, ThesisFragment
from src.mentoring.domain.student import Student
from src.mentoring.infrastructure.orm import ThesisFragmentModel
from src.mentoring.infrastructure.repositories import ThesisFragmentRepository
from src.shared.files import FileStore

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class FragmentFeedbackService:
    """Records the promoter's feedback, and takes back a mistaken upload."""

    def __init__(
        self,
        students: StudentService,
        fragment_service: FragmentService,
        fragments: ThesisFragmentRepository,
        files: FileStore,
        actions: ActionService,
    ) -> None:
        self._students = students
        self._fragment_service = fragment_service
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
        """Save the feedback; a draft that was used marks its run accepted."""
        fragment = await self._fragment_service.answer(
            caller,
            student_id,
            fragment_id,
            verdict,
            feedback,
            source_action_id,
            next_due_on,
        )
        if source_action_id is not None:
            await self._actions.mark_used(caller, student_id, source_action_id)
        return fragment

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
