"""Async repository for analysis records."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.models import AnalysisModel


class AnalysisRepository:
    """Async CRUD operations for analysis records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, model: AnalysisModel) -> None:
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)

    async def find_by_id(self, analysis_id: uuid.UUID) -> AnalysisModel | None:
        return await self._session.get(AnalysisModel, analysis_id)

    async def find_by_task_id(self, task_id: str) -> AnalysisModel | None:
        result = await self._session.execute(
            select(AnalysisModel).where(AnalysisModel.task_id == task_id)
        )
        return result.scalar_one_or_none()

    async def find_by_user(self, user_id: uuid.UUID) -> list[AnalysisModel]:
        result = await self._session.execute(
            select(AnalysisModel)
            .where(AnalysisModel.user_id == user_id)
            .order_by(AnalysisModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def find_by_user_and_task_id(
        self, user_id: uuid.UUID, task_id: str
    ) -> AnalysisModel | None:
        result = await self._session.execute(
            select(AnalysisModel).where(
                AnalysisModel.user_id == user_id,
                AnalysisModel.task_id == task_id,
            )
        )
        return result.scalar_one_or_none()
