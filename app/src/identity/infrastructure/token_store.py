"""Redis-backed blacklist for revoked tokens, access and refresh alike."""

import time

import redis.asyncio as aioredis  # type: ignore[import-untyped]
import structlog
import structlog.stdlib
from redis.exceptions import RedisError  # type: ignore[import-untyped]

from src.shared.settings import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _get_redis() -> aioredis.Redis:  # type: ignore[type-arg]
    return aioredis.from_url(settings.redis_url, decode_responses=True)  # type: ignore[no-untyped-call]


class RevokedTokenStore:
    """Blacklist for tokens identified by their jti claim.

    One namespace for both kinds: a jti is a fresh UUID either way, and the
    token's own ``type`` claim already keeps an access token out of /refresh.
    """

    def __init__(self, client: aioredis.Redis | None = None) -> None:  # type: ignore[type-arg]
        self._redis: aioredis.Redis = client or _get_redis()  # type: ignore[type-arg]

    async def revoke(self, jti: str, ttl_seconds: int) -> None:
        """Add jti to the blacklist with an expiry matching the token's TTL."""
        if ttl_seconds <= 0:
            return  # already expired — nothing left to refuse
        try:
            await self._redis.setex(f"revoked_jti:{jti}", ttl_seconds, "1")  # type: ignore[misc]
        except RedisError:
            logger.error("token_store_revoke_failed", jti=jti)

    async def retire(self, jti: str, ttl_seconds: int, grace_seconds: int) -> None:
        """Revoke jti once a grace period has passed.

        For a refresh token that has just been replaced: two tabs, or a page
        and its prefetches, can present the same one at once, and refusing the
        second would log out a browser that did nothing wrong. ``nx`` keeps
        that second use from pushing the deadline back, and from softening a
        revocation already in force.
        """
        if ttl_seconds <= 0:
            return  # already expired — nothing left to refuse
        revoked_from = time.time() + grace_seconds
        try:
            await self._redis.set(  # type: ignore[misc]
                f"revoked_jti:{jti}", str(revoked_from), ex=ttl_seconds, nx=True
            )
        except RedisError:
            logger.error("token_store_revoke_failed", jti=jti)

    async def is_revoked(self, jti: str) -> bool:
        """Return True if the jti has been blacklisted and its grace is over.

        The stored value is the moment revocation starts, so the ``"1"`` that
        ``revoke`` writes is simply a moment long past.

        Falls back to False on Redis unavailability — tokens remain usable
        until Redis recovers, which is preferable to a hard outage.
        This is a conscious security trade-off; monitor for ERROR log events.
        """
        try:
            revoked_from = await self._redis.get(f"revoked_jti:{jti}")  # type: ignore[misc]
            return revoked_from is not None and float(revoked_from) <= time.time()  # type: ignore[arg-type]
        except RedisError:
            logger.error(
                "token_store_check_failed_fail_open",
                jti=jti,
                warning="revoked token may be accepted until Redis recovers",
            )
            return False
