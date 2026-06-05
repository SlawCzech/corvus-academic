"""Async repositories for persisting gateway domain data."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.models import AnalysisModel, LoginEventModel, UserModel


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

    async def find_by_task_id(self, task_id: str) -> AnalysisModel | None:
        """Return the analysis matching a Celery task_id, or None."""
        result = await self._session.execute(
            select(AnalysisModel).where(AnalysisModel.task_id == task_id)
        )
        return result.scalar_one_or_none()

    async def find_by_user(self, user_id: uuid.UUID) -> list[AnalysisModel]:
        """Return all analyses belonging to the given user, newest first."""
        result = await self._session.execute(
            select(AnalysisModel)
            .where(AnalysisModel.user_id == user_id)
            .order_by(AnalysisModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def find_by_user_and_task_id(
        self, user_id: uuid.UUID, task_id: str
    ) -> AnalysisModel | None:
        """Return an analysis only if it belongs to the given user."""
        result = await self._session.execute(
            select(AnalysisModel).where(
                AnalysisModel.user_id == user_id,
                AnalysisModel.task_id == task_id,
            )
        )
        return result.scalar_one_or_none()


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

    async def find_all(self) -> list[UserModel]:
        """Return all users ordered by creation date."""
        result = await self._session.execute(
            select(UserModel).order_by(UserModel.created_at)
        )
        return list(result.scalars().all())

    async def delete(self, user_id: uuid.UUID) -> None:
        """Delete the user with the given id if it exists."""
        user = await self._session.get(UserModel, user_id)
        if user is not None:
            await self._session.delete(user)
            await self._session.commit()

    async def update_api_key(
        self, user_id: uuid.UUID, encrypted: str | None
    ) -> None:
        """Store the encrypted API key on the user record and commit."""
        user = await self._session.get(UserModel, user_id)
        if user is None:
            return
        user.api_key_encrypted = encrypted
        await self._session.commit()

    async def update_password(self, user_id: uuid.UUID, hashed: str) -> None:
        """Replace the hashed password on the user record and commit."""
        user = await self._session.get(UserModel, user_id)
        if user is None:
            return
        user.hashed_password = hashed
        await self._session.commit()


class LoginEventRepository:
    """Async append-only store for login audit events."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, model: LoginEventModel) -> None:
        """Persist a login event."""
        self._session.add(model)
        await self._session.commit()

    async def find_by_user(self, user_id: uuid.UUID) -> list[LoginEventModel]:
        """Return all login events for a user, newest first."""
        result = await self._session.execute(
            select(LoginEventModel)
            .where(LoginEventModel.user_id == user_id)
            .order_by(LoginEventModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def find_all(
        self,
        user_id: uuid.UUID | None = None,
        success: bool | None = None,
    ) -> list[LoginEventModel]:
        """Return login events with optional filters, newest first."""
        stmt = select(LoginEventModel).order_by(LoginEventModel.created_at.desc())
        if user_id is not None:
            stmt = stmt.where(LoginEventModel.user_id == user_id)
        if success is not None:
            stmt = stmt.where(LoginEventModel.success == success)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
