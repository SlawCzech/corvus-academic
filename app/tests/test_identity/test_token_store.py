"""RevokedTokenStore against a stand-in for the few Redis calls it makes."""

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

    async def get(self, key: str) -> str | None:
        return self.values.get(key)


@pytest.fixture
def now(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    clock = [1_000_000.0]
    monkeypatch.setattr(module.time, "time", lambda: clock[0])
    return clock


@pytest.fixture
def store() -> RevokedTokenStore:
    return RevokedTokenStore(client=FakeRedis())


async def test_unknown_token_is_not_revoked(store: RevokedTokenStore) -> None:
    assert await store.is_revoked("jti") is False


async def test_revoke_takes_effect_at_once(store: RevokedTokenStore) -> None:
    await store.revoke("jti", 60)
    assert await store.is_revoked("jti") is True


async def test_retired_token_works_until_the_grace_ends(
    store: RevokedTokenStore, now: list[float]
) -> None:
    await store.retire("jti", 3600, 30)
    assert await store.is_revoked("jti") is False

    now[0] += 30
    assert await store.is_revoked("jti") is True


async def test_a_second_retire_does_not_extend_the_grace(
    store: RevokedTokenStore, now: list[float]
) -> None:
    await store.retire("jti", 3600, 30)
    now[0] += 20
    await store.retire("jti", 3600, 30)

    now[0] += 10
    assert await store.is_revoked("jti") is True


async def test_retire_does_not_soften_a_revocation(
    store: RevokedTokenStore, now: list[float]
) -> None:
    await store.revoke("jti", 3600)
    await store.retire("jti", 3600, 30)
    assert await store.is_revoked("jti") is True
