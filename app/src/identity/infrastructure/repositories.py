"""Async repositories for persisting identity domain data."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.identity.infrastructure.models import (
    AccessRequestModel,
    LoginEventModel,
    TermsAcceptanceModel,
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

    async def update_home_university(
        self, user_id: uuid.UUID, university_id: uuid.UUID | None
    ) -> None:
        """Set or clear the user's home university and commit."""
        user = await self._session.get(UserModel, user_id)
        if user is None:
            return
        user.home_university_id = university_id
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


# How long a login event is kept: an address and a browser per attempt are
# worth having while someone may still ask about a break-in, not for ever.
# The privacy policy promises this number (`frontend/content/legal`).
LOGIN_EVENT_RETENTION = timedelta(days=90)


class LoginEventRepository:
    """Async append-only store for login audit events, kept for 90 days."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, model: LoginEventModel) -> None:
        """Persist a login event, and drop the ones past their time.

        Pruning rides on the write: every login is a moment the table is
        touched anyway, and a server nobody logs into keeps nothing new.
        """
        self._session.add(model)
        await self._session.execute(
            delete(LoginEventModel).where(
                LoginEventModel.created_at < datetime.now(UTC) - LOGIN_EVENT_RETENTION
            )
        )
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


class TermsAcceptanceRepository:
    """Who accepted which version of the terms, and when."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def accepted_at(self, user_id: uuid.UUID, version: str) -> datetime | None:
        """When the user accepted this version, or None if they have not."""
        model = await self._session.get(TermsAcceptanceModel, (user_id, version))
        return model.accepted_at if model is not None else None

    async def record(self, user_id: uuid.UUID, version: str) -> datetime:
        """Record an acceptance; accepting again keeps the first date."""
        existing = await self.accepted_at(user_id, version)
        if existing is not None:
            return existing
        model = TermsAcceptanceModel(
            user_id=user_id, version=version, accepted_at=datetime.now(UTC)
        )
        self._session.add(model)
        await self._session.commit()
        return model.accepted_at
