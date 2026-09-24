"""Use cases for running AI actions against a student.

`app` owns the whole lifecycle around the model call: it decides what the
agent may see (context assembly), records the attempt before dispatching it,
and applies whatever the promoter accepts back onto the student. The agent
only runs the graph.
"""

import uuid
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

import structlog

from src.mentoring.application.agent_client import (
    BYOK,
    AgentClient,
    AgentUnavailableError,
)
from src.mentoring.application.context import (
    assemble_check_progress_context,
    assemble_defence_questions_context,
    assemble_draft_meeting_note_context,
    assemble_evaluate_methodology_context,
    assemble_generate_review_context,
    assemble_propose_topic_context,
)
from src.mentoring.application.draft_service import to_domain as draft_to_domain
from src.mentoring.application.exceptions import (
    ActionNotFoundError,
    UnsupportedActionError,
)
from src.mentoring.application.guidelines_port import (
    GuidelineRubric,
    GuidelineSource,
)
from src.mentoring.application.model_service import ModelService
from src.mentoring.application.student_service import (
    Caller,
    StudentService,
)
from src.mentoring.domain.action import ActionStatus, ActionType, AgentAction
from src.mentoring.domain.draft import ThesisDraft
from src.mentoring.domain.student import Student
from src.mentoring.infrastructure.orm import AgentActionModel
from src.mentoring.infrastructure.repositories import (
    AgentActionRepository,
    ThesisDraftRepository,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _to_domain(model: AgentActionModel) -> AgentAction:
    stored: Any = model.output
    output = cast(dict[str, Any], stored) if isinstance(stored, dict) else None
    return AgentAction(
        id=model.id,
        student_id=model.student_id,
        promotor_id=model.promotor_id,
        action_type=ActionType(model.action_type),
        status=ActionStatus(model.status),
        task_id=model.task_id,
        detail=model.detail,
        output=output,
        error=model.error,
        accepted=model.accepted,
        accepted_at=model.accepted_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class ActionService:
    """Triggers AI actions, tracks them, and applies accepted results."""

    def __init__(
        self,
        students: StudentService,
        actions: AgentActionRepository,
        drafts: ThesisDraftRepository,
        agent: AgentClient,
        guidelines: GuidelineSource | None = None,
        models: ModelService | None = None,
    ) -> None:
        self._students = students
        self._actions = actions
        self._drafts = drafts
        self._agent = agent
        self._guidelines = guidelines
        self._models = models

    # ---------- trigger ----------

    async def trigger(
        self,
        caller: Caller,
        student_id: UUID,
        action_type: ActionType,
        token: str,
        detail: str | None = None,
        model: str | None = None,
        language: str = "pl",
        review_tone: str = "auto",
        byok: BYOK | None = None,
    ) -> AgentAction:
        """Record and dispatch one action for a student the caller can see.

        `byok` is the caller's own provider key when they have set one. It is
        forwarded and never written to the action row — the row is what the
        promoter can read back later.
        """
        student = await self._students.get(caller, student_id)
        if byok is not None:
            # The provider's own model runs; a local tag would be ignored.
            model = None
        elif self._models is not None:
            # Before anything is recorded: a refused model is a bad request,
            # not a failed action in the student's history.
            model = await self._models.resolve(model)
        context, input_ref = await self._assemble(
            caller, student, action_type, detail, review_tone
        )

        now = datetime.now(UTC)
        record = AgentActionModel(
            id=uuid.uuid4(),
            student_id=student.id,
            promotor_id=caller.user_id,
            action_type=str(action_type),
            status=str(ActionStatus.PENDING),
            detail=detail,
            # IDs only: the context itself is reproducible from these rows,
            # and the prompt can be large.
            input_ref=input_ref,
            created_at=now,
            updated_at=now,
        )
        await self._actions.save(record)

        try:
            task_id = await self._agent.submit_action(
                action_id=record.id,
                action_type=str(action_type),
                student_id=student.id,
                context=context,
                token=token,
                model=model,
                language=language,
                byok=byok,
            )
        except AgentUnavailableError as exc:
            # The attempt stays on the record — a promoter who clicked and got
            # nothing should see why, not an empty history.
            record.status = str(ActionStatus.FAILED)
            record.error = str(exc)
            await self._actions.update(record)
            logger.error(
                "action_dispatch_failed",
                action_id=str(record.id),
                action_type=str(action_type),
                error=str(exc),
            )
            raise

        record.task_id = task_id
        await self._actions.update(record)
        logger.info(
            "action_dispatched",
            action_id=str(record.id),
            action_type=str(action_type),
            task_id=task_id,
            student_id=str(student.id),
            # Which account pays for this run; never the key itself.
            byok_provider=byok.provider if byok else None,
        )
        return _to_domain(record)

    # ---------- read ----------

    async def list_actions(
        self,
        caller: Caller,
        student_id: UUID,
        token: str,
        action_type: ActionType | None = None,
    ) -> list[AgentAction]:
        """Return a student's action history, newest first.

        Unfinished actions are refreshed from the agent on the way out. The
        single-action poll is not enough on its own: a client that reloads
        the page loses the id it was polling and only ever asks for the
        list, so without this the row would stay `running` forever while
        the agent's result sits unread.
        """
        student = await self._students.get(caller, student_id)
        records = await self._actions.find_by_student(
            student.id, action_type=str(action_type) if action_type else None
        )
        return [
            await self._refresh(r, token)
            if r.task_id is not None and not ActionStatus(r.status).is_terminal
            else _to_domain(r)
            for r in records
        ]

    async def get_action(
        self,
        caller: Caller,
        student_id: UUID,
        action_id: UUID,
        token: str,
    ) -> AgentAction:
        """Return one action, refreshed from the agent if still running."""
        record = await self._require_record(caller, student_id, action_id)
        action = _to_domain(record)
        if action.is_finished or record.task_id is None:
            return action
        return await self._refresh(record, token)

    # ---------- accept ----------

    async def accept(
        self,
        caller: Caller,
        student_id: UUID,
        action_id: UUID,
        topic_index: int = 0,
    ) -> AgentAction:
        """Accept a completed action and apply its effect on the student.

        Accepting a topic proposal is what sets `Student.current_topic` — the
        model proposes, the promoter decides, and only the decision is
        denormalized onto the student.
        """
        record = await self._require_record(caller, student_id, action_id)
        action = _to_domain(record)

        # Validate everything before writing anything: an out-of-range index
        # must not leave a half-accepted action behind.
        action.accept()
        await self._apply_effect(caller, action, student_id, topic_index)

        record.accepted = action.accepted
        record.accepted_at = action.accepted_at
        await self._actions.update(record)
        logger.info(
            "action_accepted",
            action_id=str(record.id),
            action_type=record.action_type,
            student_id=str(student_id),
        )
        return _to_domain(record)

    # ---------- internals ----------

    async def _assemble(
        self,
        caller: Caller,
        student: Student,
        action_type: ActionType,
        detail: str | None,
        review_tone: str = "auto",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Gather what this action needs, and the provenance of what was used.

        Each action fetches only its own inputs — a progress check reads two
        draft rows, a topic proposal reads none. The returned ``input_ref``
        holds IDs only: the context is reproducible from those rows, and a
        thesis is far too large to log twice.
        """
        base_ref: dict[str, Any] = {"student_id": str(student.id)}

        match action_type:
            case ActionType.PROPOSE_TOPIC:
                notes = await self._students.list_meeting_notes(caller, student.id)
                return (
                    assemble_propose_topic_context(student, notes, detail),
                    base_ref | {"note_ids": [str(n.id) for n in notes]},
                )
            case ActionType.DRAFT_MEETING_NOTE:
                notes = await self._students.list_meeting_notes(caller, student.id)
                return (
                    assemble_draft_meeting_note_context(student, notes, detail),
                    base_ref | {"note_ids": [str(n.id) for n in notes]},
                )
            case ActionType.EVALUATE_METHODOLOGY:
                latest = await self._latest_drafts(student.id, 1)
                rubric = await self._rubric(student)
                return (
                    assemble_evaluate_methodology_context(
                        student,
                        latest[0] if latest else None,
                        detail,
                        guidelines=rubric.rubric_md if rubric else None,
                    ),
                    base_ref | self._draft_ref(latest[:1]) | self._rubric_ref(rubric),
                )
            case ActionType.DEFENCE_QUESTIONS:
                latest = await self._latest_drafts(student.id, 1)
                return (
                    assemble_defence_questions_context(
                        student, latest[0] if latest else None, detail
                    ),
                    base_ref | self._draft_ref(latest[:1]),
                )
            case ActionType.GENERATE_REVIEW:
                latest = await self._latest_drafts(student.id, 1)
                rubric = await self._rubric(student)
                return (
                    assemble_generate_review_context(
                        student,
                        latest[0] if latest else None,
                        detail,
                        review_tone,
                        guidelines=rubric.rubric_md if rubric else None,
                    ),
                    base_ref | self._draft_ref(latest[:1]) | self._rubric_ref(rubric),
                )
            case ActionType.CHECK_PROGRESS:
                latest = await self._latest_drafts(student.id, 2)
                return (
                    assemble_check_progress_context(student, latest, detail),
                    base_ref | self._draft_ref(latest),
                )
            case _:  # pragma: no cover — every ActionType is handled above
                raise UnsupportedActionError(
                    f"No context assembly for action type: {action_type}"
                )

    async def _rubric(self, student: Student) -> GuidelineRubric | None:
        """The rubric in force for the student's chosen guideline set."""
        if student.guideline_set_id is None or self._guidelines is None:
            return None
        return await self._guidelines.current_rubric(student.guideline_set_id)

    @staticmethod
    def _rubric_ref(rubric: GuidelineRubric | None) -> dict[str, Any]:
        """Which guideline version the action was judged against — its audit."""
        return {"guideline_version_id": str(rubric.version_id)} if rubric else {}

    async def _latest_drafts(self, student_id: UUID, limit: int) -> list[ThesisDraft]:
        models = await self._drafts.find_latest(student_id, limit=limit)
        return [draft_to_domain(m) for m in models]

    @staticmethod
    def _draft_ref(drafts: list[ThesisDraft]) -> dict[str, Any]:
        return {
            "draft_ids": [str(d.id) for d in drafts],
            "draft_versions": [d.version_number for d in drafts],
        }

    async def _apply_effect(
        self,
        caller: Caller,
        action: AgentAction,
        student_id: UUID,
        topic_index: int,
    ) -> None:
        """Write what the promoter accepted back into the student's record.

        Only two actions change anything: a topic proposal settles the topic,
        and a drafted note becomes a real meeting note — carrying
        ``source_action_id``, so an AI-drafted note stays distinguishable
        from one the promoter wrote. The rest are read-only advice.
        """
        if action.action_type is ActionType.PROPOSE_TOPIC:
            title = action.topic_title(topic_index)
            await self._students.update(caller, student_id, current_topic=title)
        elif action.action_type is ActionType.DRAFT_MEETING_NOTE:
            await self._students.add_meeting_note(
                caller,
                student_id,
                content=action.drafted_note(),
                source_action_id=action.id,
            )

    async def _require_record(
        self, caller: Caller, student_id: UUID, action_id: UUID
    ) -> AgentActionModel:
        """Load an action of a student the caller can see, or raise."""
        student = await self._students.get(caller, student_id)
        record = await self._actions.find_by_id(action_id)
        if record is None or record.student_id != student.id:
            raise ActionNotFoundError(str(action_id))
        return record

    async def _refresh(self, record: AgentActionModel, token: str) -> AgentAction:
        """Copy the agent's current view of the task onto our own row."""
        task_id = record.task_id
        if task_id is None:  # pragma: no cover — guarded by the caller
            return _to_domain(record)
        try:
            remote = await self._agent.get_action(task_id, token)
        except AgentUnavailableError as exc:
            # Polling must not fail because the agent restarted; the caller
            # keeps seeing the last known state and can poll again.
            logger.warning(
                "action_refresh_failed", action_id=str(record.id), error=str(exc)
            )
            return _to_domain(record)

        record.status = str(ActionStatus(remote.status))
        if remote.result is not None:
            record.output = remote.result
        if remote.error is not None:
            record.error = remote.error
        await self._actions.update(record)
        return _to_domain(record)
