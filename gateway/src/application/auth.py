"""JWT token creation and verification for the gateway."""

import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from src.domain.user import Role, User
from src.infrastructure.settings import settings

_ACCESS_TYPE = "access"
_REFRESH_TYPE = "refresh"


def create_access_token(user: User) -> str:
    """Create a short-lived JWT (15 min) encoding user identity."""
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "sub": str(user.id),
        "email": user.email,
        "role": str(user.role),
        "type": _ACCESS_TYPE,
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

    Raises ValueError if invalid, expired, or wrong type.
    """
    try:
        payload: dict[str, str] = jwt.decode(  # pyright: ignore[reportUnknownMemberType]
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") != _ACCESS_TYPE:
            raise ValueError("Not an access token")
        return User(
            id=UUID(payload["sub"]),
            email=payload["email"],
            role=Role(payload["role"]),
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


# Legacy alias kept for any callers that used the old name during transition.
def create_token(user: User) -> str:
    """Alias for create_access_token — preserved for backward compatibility."""
    return create_access_token(user)


def verify_token(token: str) -> User:
    """Alias for verify_access_token — preserved for backward compatibility."""
    return verify_access_token(token)
