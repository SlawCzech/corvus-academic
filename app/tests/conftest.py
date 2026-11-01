"""Environment defaults for the whole `app` test suite.

Loaded before any subdirectory conftest, so importing `main` (and therefore
`src.shared.settings`) never fails on a missing required variable.
"""

import os

os.environ.setdefault("JWT_SECRET", "test-secret-key-that-is-long-enough-32ch")
os.environ.setdefault("FERNET_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/thesis_reviewer"
)
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password-123")
os.environ.setdefault("AGENT_URL", "http://agent:8002")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")


from collections.abc import Generator  # noqa: E402

import pytest  # noqa: E402


class InMemoryTokenStore:
    """The revocation list without Redis — what every client fixture talks to.

    Autouse, because ``get_current_user`` consults it on every authenticated
    request: without it each test would try Redis, fail open and log an error.
    """

    def __init__(self) -> None:
        self.revoked: dict[str, int] = {}
        # Retired tokens still in their grace period. Tests end it by hand.
        self.retiring: set[str] = set()

    async def revoke(self, jti: str, ttl_seconds: int) -> None:
        if ttl_seconds > 0:
            self.revoked[jti] = ttl_seconds

    async def retire(self, jti: str, ttl_seconds: int, grace_seconds: int) -> None:
        if ttl_seconds > 0 and jti not in self.revoked:
            self.retiring.add(jti)

    def end_grace(self) -> None:
        self.revoked |= dict.fromkeys(self.retiring, 1)
        self.retiring.clear()

    async def is_revoked(self, jti: str) -> bool:
        return jti in self.revoked


@pytest.fixture(autouse=True)
def token_store() -> Generator[InMemoryTokenStore]:
    from main import app
    from src.identity.infrastructure.dependencies import get_token_store

    store = InMemoryTokenStore()
    app.dependency_overrides[get_token_store] = lambda: store
    yield store
    app.dependency_overrides.pop(get_token_store, None)
