"""Rotating FERNET_KEY: the stored provider keys move to the new key, or none do."""

import uuid
from collections.abc import AsyncGenerator

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from scripts.rotate_fernet_key import SameKeyError, rotate
from src.identity.infrastructure.models import Base, UserApiKeyModel, UserModel

_SCHEMA_TRANSLATE = {"schema_translate_map": {"identity": None}}
OLD = Fernet.generate_key().decode()
NEW = Fernet.generate_key().decode()


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", execution_options=_SCHEMA_TRANSLATE
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()


async def _store(session: AsyncSession, provider: str, key: str, under: str) -> None:
    user = UserModel(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4().hex}@example.com",
        role="promotor",
        hashed_password="x",
    )
    session.add(user)
    session.add(
        UserApiKeyModel(
            user_id=user.id,
            provider=provider,
            key_encrypted=Fernet(under.encode()).encrypt(key.encode()).decode(),
        )
    )
    await session.commit()


async def _plain_under(session: AsyncSession, key: str) -> list[str]:
    session.expire_all()
    rows = (await session.execute(select(UserApiKeyModel))).scalars().all()
    return sorted(
        Fernet(key.encode()).decrypt(r.key_encrypted.encode()).decode() for r in rows
    )


async def test_apply_moves_every_key_to_the_new_one(session: AsyncSession) -> None:
    await _store(session, "claude", "sk-ant-1", OLD)
    await _store(session, "openai", "sk-2", OLD)

    report = await rotate(session, OLD, NEW, apply=True)

    assert (report.rotated, report.already_new, report.unreadable) == (2, 0, [])
    assert await _plain_under(session, NEW) == ["sk-2", "sk-ant-1"]


async def test_a_dry_run_writes_nothing(session: AsyncSession) -> None:
    await _store(session, "claude", "sk-ant-1", OLD)

    report = await rotate(session, OLD, NEW, apply=False)

    assert report.rotated == 1
    assert await _plain_under(session, OLD) == ["sk-ant-1"]


async def test_a_second_run_leaves_rotated_keys_alone(session: AsyncSession) -> None:
    await _store(session, "claude", "sk-ant-1", OLD)
    await rotate(session, OLD, NEW, apply=True)

    report = await rotate(session, OLD, NEW, apply=True)

    assert (report.rotated, report.already_new) == (0, 1)
    assert await _plain_under(session, NEW) == ["sk-ant-1"]


async def test_one_unreadable_key_stops_the_whole_run(session: AsyncSession) -> None:
    await _store(session, "claude", "sk-ant-1", OLD)
    await _store(session, "openai", "sk-2", Fernet.generate_key().decode())

    report = await rotate(session, OLD, NEW, apply=True)

    assert report.rotated == 1
    assert len(report.unreadable) == 1
    assert report.unreadable[0].endswith("/openai")
    rows = (await session.execute(select(UserApiKeyModel))).scalars().all()
    claude = next(r for r in rows if r.provider == "claude")
    assert Fernet(OLD.encode()).decrypt(claude.key_encrypted.encode()) == b"sk-ant-1"


async def test_the_same_key_twice_is_refused(session: AsyncSession) -> None:
    with pytest.raises(SameKeyError):
        await rotate(session, OLD, OLD, apply=True)
