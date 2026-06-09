"""Local JWT verification for the agent service.

Identical logic to gateway — both services share JWT_SECRET and verify
tokens locally without a network call to the identity service.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

import jwt

from src.infrastructure.settings import settings

_ACCESS_TYPE = "access"


class Role(StrEnum):
    ADMIN = "admin"
    PROMOTOR = "promotor"


@dataclass(frozen=True)
class TokenUser:
    """JWT-derived user identity — decoded claims only, not a DB entity."""

    id: UUID
    email: str
    role: Role
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def verify_access_token(token: str) -> TokenUser:
    """Decode and validate an access token. Raises ValueError if invalid."""
    try:
        payload: dict[str, str] = jwt.decode(  # pyright: ignore[reportUnknownMemberType]
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") != _ACCESS_TYPE:
            raise ValueError("Not an access token")
        return TokenUser(
            id=UUID(payload["sub"]),
            email=payload["email"],
            role=Role(payload["role"]),
        )
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise ValueError(f"Invalid token: {exc}") from exc
