"""JWT token creation and verification for the gateway."""

from uuid import UUID

import jwt

from src.domain.user import Role, User
from src.infrastructure.settings import settings


def create_token(user: User) -> str:
    """Create a signed JWT access token encoding the user's identity."""
    payload: dict[str, str] = {
        "sub": str(user.id),
        "email": user.email,
        "role": str(user.role),
    }
    return jwt.encode(  # pyright: ignore[reportUnknownMemberType]
        payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )


def verify_token(token: str) -> User:
    """Decode and validate a JWT, returning the embedded User.

    Raises ValueError if the token is invalid, expired, or malformed.
    """
    try:
        payload: dict[str, str] = jwt.decode(  # pyright: ignore[reportUnknownMemberType]
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return User(
            id=UUID(payload["sub"]),
            email=payload["email"],
            role=Role(payload["role"]),
        )
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise ValueError(f"Invalid token: {exc}") from exc
