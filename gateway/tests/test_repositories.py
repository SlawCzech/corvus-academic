"""Integration tests for async repositories using in-memory SQLite."""

import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.infrastructure.models import AnalysisModel, Base, UserModel
from src.infrastructure.repositories import AnalysisRepository, UserRepository

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


# ---------- AnalysisRepository ----------


async def test_save_and_retrieve_analysis(session: AsyncSession) -> None:
    user_id = uuid.uuid4()
    user = UserModel(
        id=user_id,
        email="analyst@corvus.local",
        role="promotor",
        hashed_password="hashed",
    )
    session.add(user)
    await session.commit()

    analysis = AnalysisModel(
        id=uuid.uuid4(),
        evaluation_id="eval-abc",
        user_id=user_id,
        status="PENDING",
        result=None,
    )
    repo = AnalysisRepository(session)
    await repo.save(analysis)

    found = await repo.find_by_id(analysis.id)
    assert found is not None
    assert found.evaluation_id == "eval-abc"
    assert found.status == "PENDING"
    assert found.result is None


async def test_find_analysis_by_id_missing(session: AsyncSession) -> None:
    repo = AnalysisRepository(session)
    result = await repo.find_by_id(uuid.uuid4())
    assert result is None


async def test_save_analysis_with_result(session: AsyncSession) -> None:
    user_id = uuid.uuid4()
    user = UserModel(
        id=user_id,
        email="owner@corvus.local",
        role="admin",
        hashed_password="hashed",
    )
    session.add(user)
    await session.commit()

    analysis = AnalysisModel(
        id=uuid.uuid4(),
        evaluation_id="eval-xyz",
        user_id=user_id,
        status="SUCCESS",
        result={"score": 92, "summary": "Good work"},
    )
    repo = AnalysisRepository(session)
    await repo.save(analysis)

    found = await repo.find_by_id(analysis.id)
    assert found is not None
    assert found.result == {"score": 92, "summary": "Good work"}


# ---------- UserRepository ----------


async def test_save_and_retrieve_user(session: AsyncSession) -> None:
    user = UserModel(
        id=uuid.uuid4(),
        email="test@corvus.local",
        role="admin",
        hashed_password="hashed_pw",
    )
    repo = UserRepository(session)
    await repo.save(user)

    found = await repo.find_by_email("test@corvus.local")
    assert found is not None
    assert found.email == "test@corvus.local"
    assert found.role == "admin"
    assert found.hashed_password == "hashed_pw"


async def test_find_user_by_email_missing(session: AsyncSession) -> None:
    repo = UserRepository(session)
    result = await repo.find_by_email("nobody@example.com")
    assert result is None


async def test_user_id_is_preserved(session: AsyncSession) -> None:
    user_id = uuid.uuid4()
    user = UserModel(
        id=user_id,
        email="unique@corvus.local",
        role="promotor",
        hashed_password="pw",
    )
    repo = UserRepository(session)
    await repo.save(user)

    found = await repo.find_by_email("unique@corvus.local")
    assert found is not None
    assert found.id == user_id
