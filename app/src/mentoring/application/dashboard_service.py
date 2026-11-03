"""Use case for the dashboard's at-a-glance summary.

Deliberately not a "pending review" stat: defining that precisely (latest
draft newer than the latest completed review) is more ambiguous than it
looks, so it's left out rather than shipped approximate.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from src.mentoring.application.action_service import ActionInProgress, ActionService
from src.mentoring.application.student_service import Caller, StudentService
from src.mentoring.domain.action import ActionStatus
from src.mentoring.domain.student import StudentStatus
from src.mentoring.infrastructure.repositories import (
    AgentActionRepository,
    ThesisFragmentRepository,
    ThesisPartRepository,
)

_RECENT_ACTIVITY_SHOWN = 6


@dataclass(frozen=True)
class RecentActivity:
    student_id: UUID
    student_name: str
    action_type: str
    status: str
    updated_at: datetime


@dataclass(frozen=True)
class FragmentAwaiting:
    """A fragment the promoter still owes an answer."""

    fragment_id: UUID
    student_id: UUID
    student_name: str
    part_name: str
    round_number: int
    received_on: date


@dataclass(frozen=True)
class PartOverdue:
    """A part past its deadline, with nothing handed in for it since."""

    part_id: UUID
    student_id: UUID
    student_name: str
    part_name: str
    due_on: date


@dataclass(frozen=True)
class DashboardSummary:
    active_students: int
    without_topic: int
    actions_in_progress: int
    # Of those, the ones that will not move until the promoter does — a
    # review paused for their pick of findings. Counted above as well.
    awaiting_input: list[ActionInProgress]
    recent_activity: list[RecentActivity]
    awaiting_feedback: list[FragmentAwaiting]
    overdue_parts: list[PartOverdue]


class DashboardService:
    """Composes student and action data into one summary, per-caller scoped."""

    def __init__(
        self,
        students: StudentService,
        actions: AgentActionRepository,
        action_service: ActionService,
        parts: ThesisPartRepository,
        fragments: ThesisFragmentRepository,
    ) -> None:
        self._students = students
        self._actions = actions
        self._action_service = action_service
        self._parts = parts
        self._fragments = fragments

    async def summary(self, caller: Caller, token: str) -> DashboardSummary:
        """Stats and recent activity for the caller's students.

        "In progress" is checked with the agent, not read off our rows: a run
        that finished while nobody had the student open would otherwise be
        counted as running until someone did. It runs first, so the recent
        activity below reads the statuses it just brought up to date.
        """
        in_progress = await self._action_service.in_progress(caller, token)
        awaiting_input = [
            item
            for item in in_progress
            if item.action.status is ActionStatus.AWAITING_INPUT
        ]

        students = await self._students.list_students(caller)
        names = {s.id: s.full_name for s in students}

        active_students = sum(1 for s in students if s.status == StudentStatus.ACTIVE)
        without_topic = sum(
            1
            for s in students
            if s.status == StudentStatus.ACTIVE and s.current_topic is None
        )

        recent = await self._actions.find_recent_by_promotor(
            caller.user_id, limit=_RECENT_ACTIVITY_SHOWN
        )
        recent_activity = [
            RecentActivity(
                student_id=a.student_id,
                student_name=names.get(a.student_id, "—"),
                action_type=a.action_type,
                status=a.status,
                updated_at=a.updated_at,
            )
            for a in recent[:_RECENT_ACTIVITY_SHOWN]
        ]

        # Only students still being supervised: a graduate's last unanswered
        # fragment is nobody's to-do.
        active = {
            s.id: s.full_name for s in students if s.status == StudentStatus.ACTIVE
        }

        return DashboardSummary(
            active_students=active_students,
            without_topic=without_topic,
            actions_in_progress=len(in_progress),
            awaiting_input=awaiting_input,
            recent_activity=recent_activity,
            awaiting_feedback=await self._awaiting_feedback(active),
            overdue_parts=await self._overdue_parts(active),
        )

    async def _awaiting_feedback(
        self, students: dict[UUID, str]
    ) -> list[FragmentAwaiting]:
        fragments = await self._fragments.find_awaiting_feedback(list(students))
        parts = await self._parts.find_by_ids([f.part_id for f in fragments])
        names = {p.id: p.name for p in parts}
        return [
            FragmentAwaiting(
                fragment_id=f.id,
                student_id=f.student_id,
                student_name=students[f.student_id],
                part_name=names[f.part_id],
                round_number=f.round_number,
                received_on=f.received_on,
            )
            for f in fragments
        ]

    async def _overdue_parts(self, students: dict[UUID, str]) -> list[PartOverdue]:
        today = datetime.now(UTC).date()
        return [
            PartOverdue(
                part_id=p.id,
                student_id=p.student_id,
                student_name=students[p.student_id],
                part_name=p.name,
                due_on=p.due_on,
            )
            for p in await self._parts.find_overdue(list(students), today)
            if p.due_on is not None
        ]
