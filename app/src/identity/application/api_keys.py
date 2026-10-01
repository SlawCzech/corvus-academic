"""Reading back a user's own provider keys.

A user may keep one key per provider. Each is stored Fernet-encrypted and
only ever decrypted for the request that is about to use it. Nothing here
caches a key, and nothing logs one.
"""

from dataclasses import dataclass
from uuid import UUID

import structlog
from cryptography.fernet import InvalidToken

from src.identity.infrastructure.repositories import ApiKeyRepository
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
    """What the owner may know about their stored keys: which ones exist."""

    providers: tuple[str, ...] = ()

    @property
    def configured(self) -> bool:
        return bool(self.providers)


async def load_api_key(
    repo: ApiKeyRepository, user_id: UUID, provider: str
) -> ApiKey | None:
    """Return the user's decrypted key for one provider, or None without one.

    A key that cannot be decrypted (FERNET_KEY rotated, row corrupted) is
    treated as absent; the caller decides what a missing key means.
    """
    if provider not in SUPPORTED_PROVIDERS:
        return None
    stored = await repo.find(user_id, provider)
    if stored is None:
        return None
    try:
        plain = get_secret_service().decrypt(stored.key_encrypted)
    except InvalidToken:
        logger.error("api_key_undecryptable", user_id=str(user_id), provider=provider)
        return None
    return ApiKey(provider=provider, key=plain)


async def get_api_key_status(repo: ApiKeyRepository, user_id: UUID) -> ApiKeyStatus:
    """Return the providers the user has a key for."""
    stored = await repo.list_for_user(user_id)
    return ApiKeyStatus(
        providers=tuple(k.provider for k in stored if k.provider in SUPPORTED_PROVIDERS)
    )
