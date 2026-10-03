"""JWT token creation and verification for the identity service."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from src.identity.domain.user import Role, User
from src.shared.settings import settings

_ACCESS_TYPE = "access"
_REFRESH_TYPE = "refresh"


@dataclass(frozen=True)
class AccessClaims:
    """What a verified access token says: who, which token, and until when.

    ``jti`` and ``expires_at`` are what logging out needs — the token goes on
    the revocation list for exactly as long as it would still be accepted.
    """

    user: User
    jti: str
    expires_at: datetime


def create_access_token(user: User) -> str:
    """Create a JWT encoding user identity, valid for ACCESS_TOKEN_EXPIRE_MINUTES."""
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "sub": str(user.id),
        "email": user.email,
        "role": str(user.role),
        "type": _ACCESS_TYPE,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(  # pyright: ignore[reportUnknownMemberType]
        payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )


def create_refresh_token(user: User) -> tuple[str, str]:
    """Create a long-lived JWT (30 days) carrying only user_id.

    Returns (token, jti) so the caller can store jti for revocation.
    """
    now = datetime.now(UTC)
    jti = str(uuid.uuid4())
    payload: dict[str, object] = {
        "sub": str(user.id),
        "type": _REFRESH_TYPE,
        "jti": jti,
        "iat": now,
        "exp": now + timedelta(days=settings.refresh_token_expire_days),
    }
    token = jwt.encode(  # pyright: ignore[reportUnknownMemberType]
        payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )
    return token, jti


def verify_access_token(token: str) -> User:
    """Decode and validate an access token, returning the embedded User.

    Raises ValueError if invalid, expired, or wrong type. Does not consult the
    revocation list — ``get_current_user`` does, since that needs Redis.
    """
    return decode_access_token(token).user


def decode_access_token(token: str) -> AccessClaims:
    """Decode and validate an access token, returning its claims.

    A token without ``jti`` is rejected: it could never be revoked. Tokens
    issued before revocation existed stop working once, and the user logs in
    again.

    Raises ValueError if invalid, expired, or wrong type.
    """
    try:
        payload: dict[str, str | int] = jwt.decode(  # pyright: ignore[reportUnknownMemberType]
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "jti", "sub"]},
        )
        if payload.get("type") != _ACCESS_TYPE:
            raise ValueError("Not an access token")
        return AccessClaims(
            user=User(
                id=UUID(str(payload["sub"])),
                email=str(payload["email"]),
                role=Role(str(payload["role"])),
            ),
            jti=str(payload["jti"]),
            expires_at=datetime.fromtimestamp(int(payload["exp"]), UTC),
        )
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise ValueError(f"Invalid token: {exc}") from exc


def verify_refresh_token(token: str) -> tuple[UUID, str]:
    """Decode and validate a refresh token.

    Returns (user_id, jti). Raises ValueError if invalid or wrong type.
    """
    try:
        payload: dict[str, str] = jwt.decode(  # pyright: ignore[reportUnknownMemberType]
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") != _REFRESH_TYPE:
            raise ValueError("Not a refresh token")
        return UUID(payload["sub"]), payload["jti"]
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise ValueError(f"Invalid refresh token: {exc}") from exc
