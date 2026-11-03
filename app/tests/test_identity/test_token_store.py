"""RevokedTokenStore against a stand-in for the few Redis calls it makes."""

import uuid

import pytest

from src.identity.infrastructure import token_store as module
from src.identity.infrastructure.token_store import RevokedTokenStore


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.values[key] = value

    async def set(self, key: str, value: str, ex: int, nx: bool) -> None:
        if not nx or key not in self.values:
            self.values[key] = value

    async def mget(self, *keys: str) -> list[str | None]:
        return [self.values.get(k) for k in keys]


@pytest.fixture
def now(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    clock = [1_000_000.0]
    monkeypatch.setattr(module.time, "time", lambda: clock[0])
    return clock


@pytest.fixture
def store() -> RevokedTokenStore:
    return RevokedTokenStore(client=FakeRedis())


_USER = uuid.UUID("00000000-0000-0000-0000-00000000000a")


async def _refused(
    store: RevokedTokenStore, jti: str, issued_at: float = 999_000.0
) -> bool:
    return await store.is_revoked(jti, user_id=_USER, issued_at=issued_at)


async def test_unknown_token_is_not_revoked(store: RevokedTokenStore) -> None:
    assert await _refused(store, "jti") is False


async def test_revoke_takes_effect_at_once(store: RevokedTokenStore) -> None:
    await store.revoke("jti", 60)
    assert await _refused(store, "jti") is True


async def test_retired_token_works_until_the_grace_ends(
    store: RevokedTokenStore, now: list[float]
) -> None:
    await store.retire("jti", 3600, 30)
    assert await _refused(store, "jti") is False

    now[0] += 30
    assert await _refused(store, "jti") is True


async def test_a_second_retire_does_not_extend_the_grace(
    store: RevokedTokenStore, now: list[float]
) -> None:
    await store.retire("jti", 3600, 30)
    now[0] += 20
    await store.retire("jti", 3600, 30)

    now[0] += 10
    assert await _refused(store, "jti") is True


async def test_retire_does_not_soften_a_revocation(
    store: RevokedTokenStore, now: list[float]
) -> None:
    await store.revoke("jti", 3600)
    await store.retire("jti", 3600, 30)
    assert await _refused(store, "jti") is True


async def test_ending_sessions_refuses_tokens_issued_before(
    store: RevokedTokenStore, now: list[float]
) -> None:
    await store.end_sessions(_USER, 3600)

    assert await _refused(store, "old", issued_at=now[0] - 0.001) is True
    assert await _refused(store, "new", issued_at=now[0] + 0.001) is False


async def test_ending_sessions_leaves_other_users_alone(
    store: RevokedTokenStore, now: list[float]
) -> None:
    await store.end_sessions(uuid.uuid4(), 3600)
    assert await _refused(store, "jti", issued_at=now[0] - 1) is False
