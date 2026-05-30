"""Async repositories for persisting gateway domain data."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.models import AnalysisModel, UserModel


class AnalysisRepository:
    """Async CRUD operations for analysis records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, model: AnalysisModel) -> None:
        """Persist an analysis record and flush to the database."""
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)

    async def find_by_id(self, analysis_id: uuid.UUID) -> AnalysisModel | None:
        """Return the analysis with the given id, or None if not found."""
        return await self._session.get(AnalysisModel, analysis_id)


class UserRepository:
    """Async CRUD operations for user records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, model: UserModel) -> None:
        """Persist a user record and flush to the database."""
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)

    async def find_by_id(self, user_id: uuid.UUID) -> UserModel | None:
        """Return the user with the given id, or None if not found."""
        return await self._session.get(UserModel, user_id)

    async def find_by_email(self, email: str) -> UserModel | None:
        """Return the user with the given email, or None if not found."""
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == email)
        )
        return result.scalar_one_or_none()

    async def update_api_key(
        self, user_id: uuid.UUID, encrypted: str | None
    ) -> None:
        """Store the encrypted API key on the user record and commit."""
        user = await self._session.get(UserModel, user_id)
        if user is None:
            return
        user.api_key_encrypted = encrypted
        await self._session.commit()
