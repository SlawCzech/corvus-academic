"""Tests for reading back a user's own provider key."""

import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.identity.application.api_keys import (
    get_api_key_status,
    load_api_key,
)
from src.identity.infrastructure.models import Base, UserModel
from src.identity.infrastructure.repositories import UserRepository
from src.identity.infrastructure.secrets import get_secret_service

_SQLITE_URL = "sqlite+aiosqlite:///:memory:"
_SCHEMA_TRANSLATE = {"schema_translate_map": {"identity": None}}

USER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000b1")


@pytest.fixture
async def repo() -> AsyncGenerator[UserRepository, None]:
    engine = create_async_engine(_SQLITE_URL, execution_options=_SCHEMA_TRANSLATE)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        repository = UserRepository(session)
        await repository.save(
            UserModel(
                id=USER_ID,
                email="promotor@example.com",
                role="promotor",
                hashed_password="hashed",
            )
        )
        yield repository
    await engine.dispose()


async def test_no_key_configured(repo: UserRepository) -> None:
    assert await load_api_key(repo, USER_ID) is None


async def test_unknown_user_has_no_key(repo: UserRepository) -> None:
    assert await load_api_key(repo, uuid.uuid4()) is None


async def test_key_round_trips_through_encryption(repo: UserRepository) -> None:
    encrypted = get_secret_service().encrypt("sk-ant-user-key")
    await repo.update_api_key(USER_ID, encrypted, provider="claude")

    loaded = await load_api_key(repo, USER_ID)

    assert loaded is not None
    assert loaded.provider == "claude"
    assert loaded.key == "sk-ant-user-key"


async def test_key_is_stored_encrypted(repo: UserRepository) -> None:
    """The plaintext must not be recoverable from the row alone."""
    encrypted = get_secret_service().encrypt("sk-ant-user-key")
    await repo.update_api_key(USER_ID, encrypted, provider="claude")

    stored = await repo.find_by_id(USER_ID)

    assert stored is not None
    assert stored.api_key_encrypted is not None
    assert "sk-ant-user-key" not in stored.api_key_encrypted


async def test_key_without_a_usable_provider_is_ignored(
    repo: UserRepository,
) -> None:
    """A row from before Phase 4 has a key but no provider to call with it."""
    encrypted = get_secret_service().encrypt("sk-legacy-key")
    await repo.update_api_key(USER_ID, encrypted, provider=None)

    assert await load_api_key(repo, USER_ID) is None


async def test_undecryptable_key_falls_back_rather_than_failing(
    repo: UserRepository,
) -> None:
    """A rotated FERNET_KEY must not take every action down with it."""
    await repo.update_api_key(USER_ID, "not-a-fernet-token", provider="claude")

    assert await load_api_key(repo, USER_ID) is None


async def test_status_reports_provider_without_the_key(
    repo: UserRepository,
) -> None:
    encrypted = get_secret_service().encrypt("sk-openai-user-key")
    await repo.update_api_key(USER_ID, encrypted, provider="openai")

    status = await get_api_key_status(repo, USER_ID)

    assert status.configured is True
    assert status.provider == "openai"


async def test_removing_the_key_clears_the_provider(repo: UserRepository) -> None:
    encrypted = get_secret_service().encrypt("sk-openai-user-key")
    await repo.update_api_key(USER_ID, encrypted, provider="openai")

    await repo.update_api_key(USER_ID, None)

    status = await get_api_key_status(repo, USER_ID)
    assert status.configured is False
    assert status.provider is None
