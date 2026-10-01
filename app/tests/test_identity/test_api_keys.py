"""Tests for storing and reading back a user's own provider keys."""

import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.identity.application.api_keys import (
    get_api_key_status,
    load_api_key,
)
from src.identity.infrastructure.models import Base, UserModel
from src.identity.infrastructure.repositories import ApiKeyRepository, UserRepository
from src.identity.infrastructure.secrets import get_secret_service

_SQLITE_URL = "sqlite+aiosqlite:///:memory:"
_SCHEMA_TRANSLATE = {"schema_translate_map": {"identity": None}}

USER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000b1")
OTHER_USER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000b2")


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(_SQLITE_URL, execution_options=_SCHEMA_TRANSLATE)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        users = UserRepository(db)
        for user_id, email in (
            (USER_ID, "promotor@example.com"),
            (OTHER_USER_ID, "other@example.com"),
        ):
            await users.save(
                UserModel(
                    id=user_id, email=email, role="promotor", hashed_password="hashed"
                )
            )
        yield db
    await engine.dispose()


@pytest.fixture
def repo(session: AsyncSession) -> ApiKeyRepository:
    return ApiKeyRepository(session)


def _encrypted(plain: str) -> str:
    return get_secret_service().encrypt(plain)


async def test_no_key_configured(repo: ApiKeyRepository) -> None:
    assert await load_api_key(repo, USER_ID, "claude") is None


async def test_unknown_user_has_no_key(repo: ApiKeyRepository) -> None:
    assert await load_api_key(repo, uuid.uuid4(), "claude") is None


async def test_key_round_trips_through_encryption(repo: ApiKeyRepository) -> None:
    await repo.upsert(USER_ID, "claude", _encrypted("sk-ant-user-key"))

    loaded = await load_api_key(repo, USER_ID, "claude")

    assert loaded is not None
    assert loaded.provider == "claude"
    assert loaded.key == "sk-ant-user-key"


async def test_key_is_stored_encrypted(repo: ApiKeyRepository) -> None:
    """The plaintext must not be recoverable from the row alone."""
    await repo.upsert(USER_ID, "claude", _encrypted("sk-ant-user-key"))

    stored = await repo.find(USER_ID, "claude")

    assert stored is not None
    assert "sk-ant-user-key" not in stored.key_encrypted


async def test_a_key_per_provider_side_by_side(repo: ApiKeyRepository) -> None:
    """Saving an OpenAI key must not cost the promoter their Anthropic one."""
    await repo.upsert(USER_ID, "claude", _encrypted("sk-ant-user-key"))
    await repo.upsert(USER_ID, "openai", _encrypted("sk-openai-user-key"))

    claude = await load_api_key(repo, USER_ID, "claude")
    openai = await load_api_key(repo, USER_ID, "openai")

    assert claude is not None and claude.key == "sk-ant-user-key"
    assert openai is not None and openai.key == "sk-openai-user-key"


async def test_saving_again_replaces_that_providers_key_only(
    repo: ApiKeyRepository,
) -> None:
    await repo.upsert(USER_ID, "claude", _encrypted("sk-ant-old"))
    await repo.upsert(USER_ID, "openai", _encrypted("sk-openai-user-key"))

    await repo.upsert(USER_ID, "claude", _encrypted("sk-ant-new"))

    claude = await load_api_key(repo, USER_ID, "claude")
    openai = await load_api_key(repo, USER_ID, "openai")
    assert claude is not None and claude.key == "sk-ant-new"
    assert openai is not None and openai.key == "sk-openai-user-key"
    assert len(await repo.list_for_user(USER_ID)) == 2


async def test_a_key_is_its_owners_alone(repo: ApiKeyRepository) -> None:
    await repo.upsert(USER_ID, "claude", _encrypted("sk-ant-user-key"))

    assert await load_api_key(repo, OTHER_USER_ID, "claude") is None


async def test_unsupported_provider_has_no_key(repo: ApiKeyRepository) -> None:
    await repo.upsert(USER_ID, "deepmind", _encrypted("sk-something"))

    assert await load_api_key(repo, USER_ID, "deepmind") is None
    assert (await get_api_key_status(repo, USER_ID)).providers == ()


async def test_undecryptable_key_counts_as_absent(repo: ApiKeyRepository) -> None:
    """A rotated FERNET_KEY must not raise from every action; the key is gone."""
    await repo.upsert(USER_ID, "claude", "not-a-fernet-token")

    assert await load_api_key(repo, USER_ID, "claude") is None


async def test_status_lists_the_providers_without_the_keys(
    repo: ApiKeyRepository,
) -> None:
    await repo.upsert(USER_ID, "openai", _encrypted("sk-openai-user-key"))
    await repo.upsert(USER_ID, "claude", _encrypted("sk-ant-user-key"))

    status = await get_api_key_status(repo, USER_ID)

    assert status.configured is True
    assert status.providers == ("claude", "openai")


async def test_removing_one_key_leaves_the_other(repo: ApiKeyRepository) -> None:
    await repo.upsert(USER_ID, "claude", _encrypted("sk-ant-user-key"))
    await repo.upsert(USER_ID, "openai", _encrypted("sk-openai-user-key"))

    assert await repo.delete(USER_ID, "openai") is True

    status = await get_api_key_status(repo, USER_ID)
    assert status.providers == ("claude",)
    # Removing what is not there is not an error.
    assert await repo.delete(USER_ID, "openai") is False


async def test_status_without_keys(repo: ApiKeyRepository) -> None:
    status = await get_api_key_status(repo, USER_ID)

    assert status.configured is False
    assert status.providers == ()


async def test_deleting_a_user_takes_their_keys(
    session: AsyncSession, repo: ApiKeyRepository
) -> None:
    await repo.upsert(USER_ID, "claude", _encrypted("sk-ant-user-key"))
    await repo.upsert(OTHER_USER_ID, "claude", _encrypted("sk-ant-other-key"))

    await UserRepository(session).delete(USER_ID)

    assert await repo.list_for_user(USER_ID) == []
    assert len(await repo.list_for_user(OTHER_USER_ID)) == 1
