"""Async repositories for persisting identity domain data."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.identity.infrastructure.models import (
    AccessRequestModel,
    LoginEventModel,
    UserApiKeyModel,
    UserModel,
)


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
            # Their keys go with them — said here rather than left to the
            # foreign key's cascade, so it holds on every database.
            await self._session.execute(
                delete(UserApiKeyModel).where(UserApiKeyModel.user_id == user_id)
            )
            await self._session.delete(user)
            await self._session.commit()

    async def update_password(self, user_id: uuid.UUID, hashed: str) -> None:
        """Replace the hashed password on the user record and commit."""
        user = await self._session.get(UserModel, user_id)
        if user is None:
            return
        user.hashed_password = hashed
        await self._session.commit()


class ApiKeyRepository:
    """Async store for users' own provider keys — one per user and provider."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find(self, user_id: uuid.UUID, provider: str) -> UserApiKeyModel | None:
        return await self._session.get(UserApiKeyModel, (user_id, provider))

    async def list_for_user(self, user_id: uuid.UUID) -> list[UserApiKeyModel]:
        result = await self._session.execute(
            select(UserApiKeyModel)
            .where(UserApiKeyModel.user_id == user_id)
            .order_by(UserApiKeyModel.provider)
        )
        return list(result.scalars().all())

    async def upsert(self, user_id: uuid.UUID, provider: str, encrypted: str) -> None:
        """Store the user's key for one provider, replacing an earlier one.

        The user's key for any other provider is left alone.
        """
        existing = await self.find(user_id, provider)
        if existing is None:
            self._session.add(
                UserApiKeyModel(
                    user_id=user_id, provider=provider, key_encrypted=encrypted
                )
            )
        else:
            existing.key_encrypted = encrypted
            existing.updated_at = datetime.now(UTC)
        await self._session.commit()

    async def delete(self, user_id: uuid.UUID, provider: str) -> bool:
        """Remove the user's key for one provider; False if there was none."""
        existing = await self.find(user_id, provider)
        if existing is None:
            return False
        await self._session.delete(existing)
        await self._session.commit()
        return True


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


class AccessRequestRepository:
    """Async CRUD for pending access requests."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, model: AccessRequestModel) -> None:
        """Persist a new access request."""
        self._session.add(model)
        await self._session.commit()

    async def find_all(self) -> list[AccessRequestModel]:
        """Return all pending requests, newest first."""
        result = await self._session.execute(
            select(AccessRequestModel).order_by(AccessRequestModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete(self, request_id: uuid.UUID) -> bool:
        """Remove one request. Returns False if it was already gone."""
        model = await self._session.get(AccessRequestModel, request_id)
        if model is None:
            return False
        await self._session.delete(model)
        await self._session.commit()
        return True
