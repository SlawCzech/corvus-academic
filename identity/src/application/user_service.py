"""Use cases for user management."""

import uuid
from datetime import UTC, datetime
from uuid import UUID

import bcrypt

from src.domain.user import Role, User, UserRegistration
from src.infrastructure.models import UserModel
from src.infrastructure.repositories import UserRepository


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _to_domain(model: UserModel) -> User:
    return User(
        id=model.id,
        email=model.email,
        role=Role(model.role),
        created_at=model.created_at,
    )


class UserService:
    """Orchestrates registration, authentication, and user management."""

    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def register(self, registration: UserRegistration) -> User:
        """Persist a new user. Raises ValueError on duplicate email."""
        existing = await self._repo.find_by_email(registration.email)
        if existing is not None:
            raise ValueError(f"Email already registered: {registration.email}")
        model = UserModel(
            id=uuid.uuid4(),
            email=registration.email,
            role=str(registration.role),
            hashed_password=registration.hashed_password,
            created_at=datetime.now(UTC),
        )
        await self._repo.save(model)
        return _to_domain(model)

    async def authenticate(self, email: str, password: str) -> User | None:
        """Return User if credentials match, otherwise None."""
        model = await self._repo.find_by_email(email)
        if model is None:
            return None
        if not _verify_password(password, model.hashed_password):
            return None
        return _to_domain(model)

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Return User for the given id, or None."""
        model = await self._repo.find_by_id(user_id)
        return _to_domain(model) if model is not None else None

    async def list_all(self) -> list[User]:
        """Return all users — intended for ADMIN use only."""
        return [_to_domain(m) for m in await self._repo.find_all()]

    async def delete(self, user_id: UUID) -> None:
        """Delete user — intended for ADMIN use only."""
        await self._repo.delete(user_id)

    async def change_password(self, user_id: UUID, new_password: str) -> None:
        """Hash and store a new password for the given user."""
        hashed = _hash_password(new_password)
        await self._repo.update_password(user_id, hashed)

    @staticmethod
    def hash_password(plain: str) -> str:
        """Hash a plaintext password — used by registration endpoints."""
        return _hash_password(plain)
