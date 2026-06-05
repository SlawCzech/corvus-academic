"""Domain entities for the identity bounded context."""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID


class Role(StrEnum):
    """User role within the Corvus system."""

    ADMIN = "admin"
    PROMOTOR = "promotor"


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_email(email: str) -> None:
    """Raise ValueError if the email format is invalid."""
    if not _EMAIL_RE.match(email):
        raise ValueError(f"Invalid email format: {email!r}")


@dataclass(frozen=True)
class User:
    """Authenticated user with a role."""

    id: UUID
    email: str
    role: Role
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class UserRegistration:
    """Value object carrying validated registration input.

    Hashing happens in infrastructure before this object is created —
    plaintext never crosses the domain boundary.
    """

    email: str
    hashed_password: str
    role: Role = Role.PROMOTOR
