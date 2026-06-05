"""Integration tests for async repositories using in-memory SQLite."""

import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.infrastructure.models import AnalysisModel, Base, LoginEventModel, UserModel
from src.infrastructure.repositories import (
    AnalysisRepository,
    LoginEventRepository,
    UserRepository,
)

_SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a fresh AsyncSession backed by an in-memory SQLite database."""
    engine = create_async_engine(_SQLITE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


def _make_user(email: str = "test@corvus.local", role: str = "promotor") -> UserModel:
    return UserModel(id=uuid.uuid4(), email=email, role=role, hashed_password="hashed")


# ---------- AnalysisRepository ----------


async def test_save_and_retrieve_analysis(session: AsyncSession) -> None:
    user = _make_user()
    session.add(user)
    await session.commit()

    analysis = AnalysisModel(
        id=uuid.uuid4(),
        evaluation_id="eval-abc",
        task_id="celery-task-1",
        user_id=user.id,
        status="PENDING",
    )
    repo = AnalysisRepository(session)
    await repo.save(analysis)

    found = await repo.find_by_id(analysis.id)
    assert found is not None
    assert found.evaluation_id == "eval-abc"
    assert found.task_id == "celery-task-1"
    assert found.status == "PENDING"


async def test_find_analysis_by_task_id(session: AsyncSession) -> None:
    user = _make_user()
    session.add(user)
    await session.commit()

    analysis = AnalysisModel(
        id=uuid.uuid4(),
        evaluation_id="eval-x",
        task_id="celery-42",
        user_id=user.id,
        status="SUCCESS",
    )
    repo = AnalysisRepository(session)
    await repo.save(analysis)

    found = await repo.find_by_task_id("celery-42")
    assert found is not None
    assert found.id == analysis.id


async def test_find_analysis_by_task_id_missing(session: AsyncSession) -> None:
    repo = AnalysisRepository(session)
    assert await repo.find_by_task_id("nonexistent") is None


async def test_find_analyses_by_user(session: AsyncSession) -> None:
    user_a = _make_user("a@x.com")
    user_b = _make_user("b@x.com")
    session.add(user_a)
    session.add(user_b)
    await session.commit()

    repo = AnalysisRepository(session)
    for i in range(3):
        await repo.save(
            AnalysisModel(
                id=uuid.uuid4(),
                evaluation_id=f"e{i}",
                task_id=f"t{i}",
                user_id=user_a.id,
                status="PENDING",
            )
        )
    await repo.save(
        AnalysisModel(
            id=uuid.uuid4(),
            evaluation_id="other",
            task_id="other",
            user_id=user_b.id,
            status="PENDING",
        )
    )

    results = await repo.find_by_user(user_a.id)
    assert len(results) == 3
    assert all(r.user_id == user_a.id for r in results)


async def test_find_by_user_and_task_id_ownership(session: AsyncSession) -> None:
    owner = _make_user("owner@x.com")
    other = _make_user("other@x.com")
    session.add(owner)
    session.add(other)
    await session.commit()

    repo = AnalysisRepository(session)
    await repo.save(
        AnalysisModel(
            id=uuid.uuid4(),
            evaluation_id="e1",
            task_id="task-abc",
            user_id=owner.id,
            status="PENDING",
        )
    )

    assert await repo.find_by_user_and_task_id(owner.id, "task-abc") is not None
    assert await repo.find_by_user_and_task_id(other.id, "task-abc") is None


async def test_find_analysis_by_id_missing(session: AsyncSession) -> None:
    repo = AnalysisRepository(session)
    assert await repo.find_by_id(uuid.uuid4()) is None


# ---------- UserRepository ----------


async def test_save_and_retrieve_user(session: AsyncSession) -> None:
    user = _make_user("test@corvus.local", "admin")
    repo = UserRepository(session)
    await repo.save(user)

    found = await repo.find_by_email("test@corvus.local")
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
        id=user_id, email="unique@corvus.local", role="promotor", hashed_password="pw"
    )
    repo = UserRepository(session)
    await repo.save(user)
    found = await repo.find_by_email("unique@corvus.local")
    assert found is not None
    assert found.id == user_id


# ---------- LoginEventRepository ----------


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
