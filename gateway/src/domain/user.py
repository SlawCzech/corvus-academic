"""Domain entities for the identity bounded context."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class Role(StrEnum):
    """User role within the Corvus system."""

    ADMIN = "admin"
    PROMOTOR = "promotor"


@dataclass(frozen=True)
class User:
    """Authenticated user with a role."""

    id: UUID
    email: str
    role: Role
