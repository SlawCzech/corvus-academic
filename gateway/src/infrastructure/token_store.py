"""Redis-backed blacklist for revoked refresh tokens."""

import redis.asyncio as aioredis  # type: ignore[import-untyped]

from src.infrastructure.settings import settings


def _get_redis() -> aioredis.Redis:  # type: ignore[type-arg]
    return aioredis.from_url(settings.redis_url, decode_responses=True)  # type: ignore[no-untyped-call]


class RefreshTokenStore:
    """Blacklist for refresh tokens identified by their jti claim."""

    def __init__(self, client: aioredis.Redis | None = None) -> None:  # type: ignore[type-arg]
        self._redis: aioredis.Redis = client or _get_redis()  # type: ignore[type-arg]

    async def revoke(self, jti: str, ttl_seconds: int) -> None:
        """Add jti to the blacklist with an expiry matching the token's TTL."""
        await self._redis.setex(f"revoked_jti:{jti}", ttl_seconds, "1")  # type: ignore[misc]

    async def is_revoked(self, jti: str) -> bool:
        """Return True if the jti has been blacklisted."""
        return await self._redis.exists(f"revoked_jti:{jti}") > 0  # type: ignore[misc]
