"""Unit tests for UserService using in-memory SQLite."""

import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.application.user_service import UserService
from src.domain.user import Role, UserRegistration
from src.infrastructure.models import Base
from src.infrastructure.repositories import UserRepository

_SQLITE_URL = "sqlite+aiosqlite:///:memory:"
_SCHEMA_TRANSLATE = {"schema_translate_map": {"identity": None}}


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(_SQLITE_URL, execution_options=_SCHEMA_TRANSLATE)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest.fixture
async def svc(session: AsyncSession) -> UserService:
    return UserService(UserRepository(session))


def _reg(
    email: str = "user@example.com", role: Role = Role.PROMOTOR
) -> UserRegistration:
    return UserRegistration(
        email=email,
        hashed_password=UserService.hash_password("secret123"),
        role=role,
    )


async def test_register_creates_user(svc: UserService) -> None:
    user = await svc.register(_reg())
    assert user.email == "user@example.com"
    assert user.role == Role.PROMOTOR
    assert isinstance(user.id, uuid.UUID)


async def test_register_duplicate_email_raises(svc: UserService) -> None:
    await svc.register(_reg())
    with pytest.raises(ValueError, match="already registered"):
        await svc.register(_reg())


async def test_register_invalid_email_raises(svc: UserService) -> None:
    with pytest.raises(ValueError, match="Invalid email"):
        await svc.register(
            UserRegistration(
                email="not-an-email",
                hashed_password=UserService.hash_password("pass"),
            )
        )


async def test_authenticate_valid_credentials(svc: UserService) -> None:
    await svc.register(_reg())
    user = await svc.authenticate("user@example.com", "secret123")
    assert user is not None
    assert user.email == "user@example.com"


async def test_authenticate_wrong_password(svc: UserService) -> None:
    await svc.register(_reg())
    user = await svc.authenticate("user@example.com", "wrong")
    assert user is None


async def test_authenticate_unknown_email(svc: UserService) -> None:
    user = await svc.authenticate("nobody@example.com", "pass")
    assert user is None


async def test_get_by_id_found(svc: UserService) -> None:
    created = await svc.register(_reg())
    found = await svc.get_by_id(created.id)
    assert found is not None
    assert found.id == created.id


async def test_get_by_id_missing(svc: UserService) -> None:
    assert await svc.get_by_id(uuid.uuid4()) is None


async def test_list_all(svc: UserService) -> None:
    await svc.register(_reg("a@x.com"))
    await svc.register(_reg("b@x.com"))
    users = await svc.list_all()
    assert len(users) == 2


async def test_delete_removes_user(svc: UserService) -> None:
    user = await svc.register(_reg())
    await svc.delete(user.id)
    assert await svc.get_by_id(user.id) is None


async def test_change_password(svc: UserService) -> None:
    user = await svc.register(_reg())
    await svc.change_password(user.id, "new-password")
    assert await svc.authenticate("user@example.com", "new-password") is not None
    assert await svc.authenticate("user@example.com", "secret123") is None
