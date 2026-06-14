"""Integration tests for identity repositories using in-memory SQLite."""

import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.infrastructure.models import Base, LoginEventModel, UserModel
from src.infrastructure.repositories import LoginEventRepository, UserRepository

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


def _make_user(email: str = "test@example.com", role: str = "promotor") -> UserModel:
    return UserModel(id=uuid.uuid4(), email=email, role=role, hashed_password="hashed")


async def test_save_and_retrieve_user(session: AsyncSession) -> None:
    user = _make_user("test@example.com", "admin")
    repo = UserRepository(session)
    await repo.save(user)

    found = await repo.find_by_email("test@example.com")
    assert found is not None
    assert found.role == "admin"


async def test_find_user_by_email_missing(session: AsyncSession) -> None:
    repo = UserRepository(session)
    assert await repo.find_by_email("nobody@example.com") is None


async def test_find_all_users(session: AsyncSession) -> None:
    repo = UserRepository(session)
    await repo.save(_make_user("a@x.com"))
    await repo.save(_make_user("b@x.com"))
    all_users = await repo.find_all()
    assert len(all_users) == 2


async def test_delete_user(session: AsyncSession) -> None:
    user = _make_user()
    repo = UserRepository(session)
    await repo.save(user)
    await repo.delete(user.id)
    assert await repo.find_by_id(user.id) is None


async def test_update_password(session: AsyncSession) -> None:
    user = _make_user()
    repo = UserRepository(session)
    await repo.save(user)
    await repo.update_password(user.id, "new_hashed_pw")
    found = await repo.find_by_id(user.id)
    assert found is not None
    assert found.hashed_password == "new_hashed_pw"


async def test_user_id_is_preserved(session: AsyncSession) -> None:
    user_id = uuid.uuid4()
    user = UserModel(
        id=user_id, email="unique@example.com", role="promotor", hashed_password="pw"
    )
    repo = UserRepository(session)
    await repo.save(user)
    found = await repo.find_by_email("unique@example.com")
    assert found is not None
    assert found.id == user_id


async def test_save_login_event(session: AsyncSession) -> None:
    user = _make_user()
    session.add(user)
    await session.commit()

    repo = LoginEventRepository(session)
    event = LoginEventModel(
        id=uuid.uuid4(),
        user_id=user.id,
        email=user.email,
        success=True,
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    await repo.save(event)

    events = await repo.find_by_user(user.id)
    assert len(events) == 1
    assert events[0].success is True


async def test_find_all_login_events_filtered(session: AsyncSession) -> None:
    user = _make_user()
    session.add(user)
    await session.commit()

    repo = LoginEventRepository(session)
    for success in [True, True, False]:
        await repo.save(
            LoginEventModel(
                id=uuid.uuid4(),
                user_id=user.id,
                email=user.email,
                success=success,
                ip_address="10.0.0.1",
            )
        )

    all_events = await repo.find_all()
    assert len(all_events) == 3

    successes = await repo.find_all(success=True)
    assert len(successes) == 2

    failures = await repo.find_all(success=False)
    assert len(failures) == 1
