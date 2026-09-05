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
    AgentClient,
    AgentUnavailableError,
)
from src.mentoring.application.context import assemble_propose_topic_context
from src.mentoring.application.student_service import (
    Caller,
    StudentService,
)
from src.mentoring.domain.action import ActionStatus, ActionType, AgentAction
from src.mentoring.domain.student import MeetingNote, Student
from src.mentoring.infrastructure.models import AgentActionModel
from src.mentoring.infrastructure.repositories import AgentActionRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class ActionNotFoundError(Exception):
    """Raised when an action does not exist, or belongs to another student."""


class UnsupportedActionError(Exception):
    """Raised for an action type `app` cannot assemble a context for yet."""


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


def _build_context(
    action_type: ActionType,
    student: Student,
    notes: list[MeetingNote],
    detail: str | None,
) -> dict[str, Any]:
    """Assemble the context for one action type.

    Each new action type adds a case here and a function in `context.py` —
    the rest of this service does not change.
    """
    if action_type is ActionType.PROPOSE_TOPIC:
        return assemble_propose_topic_context(student, notes, detail)
    raise UnsupportedActionError(
        f"No context assembly for action type: {action_type}"
    )


class ActionService:
    """Triggers AI actions, tracks them, and applies accepted results."""

    def __init__(
        self,
        students: StudentService,
        actions: AgentActionRepository,
        agent: AgentClient,
    ) -> None:
        self._students = students
        self._actions = actions
        self._agent = agent

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
    ) -> AgentAction:
        """Record and dispatch one action for a student the caller can see."""
        student = await self._students.get(caller, student_id)
        notes = await self._students.list_meeting_notes(caller, student_id)
        context = _build_context(action_type, student, notes, detail)

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
            input_ref={
                "student_id": str(student.id),
                "note_ids": [str(n.id) for n in notes],
            },
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
        )
        return _to_domain(record)

    # ---------- read ----------

    async def list_actions(
        self,
        caller: Caller,
        student_id: UUID,
        action_type: ActionType | None = None,
    ) -> list[AgentAction]:
        """Return a student's action history, newest first."""
        student = await self._students.get(caller, student_id)
        records = await self._actions.find_by_student(
            student.id, action_type=str(action_type) if action_type else None
        )
        return [_to_domain(r) for r in records]

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
        if action.action_type is ActionType.PROPOSE_TOPIC:
            title = action.topic_title(topic_index)
            await self._students.update(caller, student_id, current_topic=title)

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

    async def _require_record(
        self, caller: Caller, student_id: UUID, action_id: UUID
    ) -> AgentActionModel:
        """Load an action of a student the caller can see, or raise."""
        student = await self._students.get(caller, student_id)
        record = await self._actions.find_by_id(action_id)
        if record is None or record.student_id != student.id:
            raise ActionNotFoundError(str(action_id))
        return record

    async def _refresh(
        self, record: AgentActionModel, token: str
    ) -> AgentAction:
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
