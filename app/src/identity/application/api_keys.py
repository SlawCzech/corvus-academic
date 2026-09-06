"""Reading back a user's own provider key.

The key is stored Fernet-encrypted and only ever decrypted for the request
that is about to use it. Nothing here caches it, and nothing logs it.
"""

from dataclasses import dataclass
from uuid import UUID

import structlog
from cryptography.fernet import InvalidToken

from src.identity.infrastructure.repositories import UserRepository
from src.identity.infrastructure.secrets import get_secret_service

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Providers a user may bring a key for; mirrors the agent's own list, because
# the two services share a contract rather than a codebase.
SUPPORTED_PROVIDERS: frozenset[str] = frozenset({"claude", "openai"})


@dataclass(frozen=True)
class ApiKey:
    """A decrypted provider key, for one call."""

    provider: str
    key: str


@dataclass(frozen=True)
class ApiKeyStatus:
    """What the owner may know about their stored key: that it exists."""

    configured: bool
    provider: str | None = None


async def load_api_key(repo: UserRepository, user_id: UUID) -> ApiKey | None:
    """Return the user's decrypted key, or None if they have not set one.

    A key that cannot be decrypted (FERNET_KEY rotated, row corrupted) is
    treated as absent: the action still runs, on the self-hosted model.
    """
    user = await repo.find_by_id(user_id)
    if user is None or user.api_key_encrypted is None:
        return None
    if user.api_key_provider not in SUPPORTED_PROVIDERS:
        logger.warning(
            "api_key_without_usable_provider",
            user_id=str(user_id),
            provider=user.api_key_provider,
        )
        return None
    try:
        plain = get_secret_service().decrypt(user.api_key_encrypted)
    except InvalidToken:
        logger.error("api_key_undecryptable", user_id=str(user_id))
        return None
    return ApiKey(provider=user.api_key_provider, key=plain)


async def get_api_key_status(repo: UserRepository, user_id: UUID) -> ApiKeyStatus:
    """Return whether a key is configured, and for which provider."""
    user = await repo.find_by_id(user_id)
    if user is None or user.api_key_encrypted is None:
        return ApiKeyStatus(configured=False)
    return ApiKeyStatus(configured=True, provider=user.api_key_provider)
