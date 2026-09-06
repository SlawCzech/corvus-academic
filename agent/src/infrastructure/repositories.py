"""Async repository for agent task records."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.models import AgentTaskModel


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

    async def update_status(
        self,
        task_id: str,
        status: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> bool:
        """Write a task's status (and outcome) to its row.

        Returns False when no row matches — the caller decides whether that is
        worth an alert. ``result`` and ``error`` are only written when given,
        so a "running" update never clears an earlier value.
        """
        model = await self.find_by_task_id(task_id)
        if model is None:
            return False
        model.status = status
        if result is not None:
            model.result = result
        if error is not None:
            model.error = error
        model.updated_at = datetime.now(UTC)
        await self._session.commit()
        return True
