"""Use case for the dashboard's at-a-glance summary.

Deliberately not a "pending review" stat: defining that precisely (latest
draft newer than the latest completed review) is more ambiguous than it
looks, so it's left out rather than shipped approximate.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.mentoring.application.student_service import Caller, StudentService
from src.mentoring.domain.student import StudentStatus
from src.mentoring.infrastructure.repositories import AgentActionRepository

_RECENT_LIMIT = 30
_RECENT_ACTIVITY_SHOWN = 6
_IN_PROGRESS_STATUSES = {"pending", "running"}


@dataclass(frozen=True)
class RecentActivity:
    student_id: UUID
    student_name: str
    action_type: str
    status: str
    updated_at: datetime


@dataclass(frozen=True)
class DashboardSummary:
    active_students: int
    without_topic: int
    actions_in_progress: int
    recent_activity: list[RecentActivity]


class DashboardService:
    """Composes student and action data into one summary, per-caller scoped."""

    def __init__(
        self,
        students: StudentService,
        actions: AgentActionRepository,
    ) -> None:
        self._students = students
        self._actions = actions

    async def summary(self, caller: Caller) -> DashboardSummary:
        students = await self._students.list_students(caller)
        names = {s.id: s.full_name for s in students}

        active_students = sum(1 for s in students if s.status == StudentStatus.ACTIVE)
        without_topic = sum(
            1
            for s in students
            if s.status == StudentStatus.ACTIVE and s.current_topic is None
        )

        promotor_filter = None if caller.can_view_all else caller.user_id
        recent = await self._actions.find_recent_by_promotor(
            promotor_filter, limit=_RECENT_LIMIT
        )
        actions_in_progress = sum(
            1 for a in recent if a.status in _IN_PROGRESS_STATUSES
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

        return DashboardSummary(
            active_students=active_students,
            without_topic=without_topic,
            actions_in_progress=actions_in_progress,
            recent_activity=recent_activity,
        )
