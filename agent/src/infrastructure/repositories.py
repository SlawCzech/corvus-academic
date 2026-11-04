"""Async repositories for the agent's own tables."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.action import TaskStatus
from src.infrastructure.models import AgentTaskModel
from src.infrastructure.usage import Usage, merge_usage


class AgentTaskRepository:
    """Async CRUD operations for agent task records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, model: AgentTaskModel) -> None:
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)

    async def find_by_id(self, task_row_id: uuid.UUID) -> AgentTaskModel | None:
        return await self._session.get(AgentTaskModel, task_row_id)

    async def find_by_task_id(self, task_id: str) -> AgentTaskModel | None:
        result = await self._session.execute(
            select(AgentTaskModel).where(AgentTaskModel.task_id == task_id)
        )
        return result.scalar_one_or_none()

    async def find_by_user_and_task_id(
        self, user_id: uuid.UUID, task_id: str
    ) -> AgentTaskModel | None:
        result = await self._session.execute(
            select(AgentTaskModel).where(
                AgentTaskModel.user_id == user_id,
                AgentTaskModel.task_id == task_id,
            )
        )
        return result.scalar_one_or_none()

    async def find_by_student(
        self, student_id: uuid.UUID, user_id: uuid.UUID | None = None
    ) -> list[AgentTaskModel]:
        """A student's tasks — only ``user_id``'s, unless it is None (admin)."""
        stmt = select(AgentTaskModel).where(AgentTaskModel.student_id == student_id)
        if user_id is not None:
            stmt = stmt.where(AgentTaskModel.user_id == user_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, models: Sequence[AgentTaskModel]) -> None:
        """Delete these task rows, result and all, in one commit."""
        for model in models:
            await self._session.delete(model)
        await self._session.commit()

    async def update_status(
        self,
        task_id: str,
        status: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        error_code: str | None = None,
    ) -> bool:
        """Write a task's status (and outcome) to its row.

        Returns False when no row matches — the caller decides whether that is
        worth an alert. ``result`` and ``error`` are only written when given,
        so a "running" update never clears an earlier value.

        A cancelled task stays cancelled: revoking a task that is already on
        a worker races with that worker's own final write, and the promoter's
        decision has to win it.
        """
        model = await self.find_by_task_id(task_id)
        if model is None:
            return False
        if model.status == TaskStatus.CANCELLED and status != TaskStatus.CANCELLED:
            return True
        model.status = status
        if result is not None:
            model.result = result
        if error is not None:
            model.error = error
        if error_code is not None:
            model.error_code = error_code
        model.updated_at = datetime.now(UTC)
        await self._session.commit()
        return True

    async def update_progress(self, task_id: str, progress: dict[str, Any]) -> bool:
        """Record how far a running task has got.

        Written only while the task is still pending or running: a progress
        write that lands after the final status — or after a cancel — must
        not make a finished task look like it is still going.
        """
        model = await self.find_by_task_id(task_id)
        if model is None:
            return False
        if model.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
            return True
        model.progress = progress
        model.updated_at = datetime.now(UTC)
        await self._session.commit()
        return True

    async def add_usage(self, task_id: str, usage: Usage) -> bool:
        """Add one run's tokens to what the task has spent so far.

        Written whatever the status — a cancelled run spent its tokens too.
        """
        model = await self.find_by_task_id(task_id)
        if model is None:
            return False
        model.usage = merge_usage(model.usage, usage)
        await self._session.commit()
        return True
