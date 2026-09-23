"""Domain entities for the identity bounded context."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from email_validator import EmailNotValidError
from email_validator import validate_email as _validate_email_lib


class Role(StrEnum):
    """User role within the Corvus system."""

    ADMIN = "admin"
    PROMOTOR = "promotor"


class Permission(StrEnum):
    """Fine-grained permissions granted to roles."""

    MANAGE_USERS = "manage_users"
    VIEW_ALL_ANALYSES = "view_all_analyses"
    SUBMIT_ANALYSIS = "submit_analysis"
    MANAGE_STUDENTS = "manage_students"
    VIEW_ALL_STUDENTS = "view_all_students"
    MANAGE_GUIDELINES = "manage_guidelines"


_ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),
    Role.PROMOTOR: frozenset(
        {Permission.SUBMIT_ANALYSIS, Permission.MANAGE_STUDENTS}
    ),
}


@dataclass(frozen=True)
class User:
    """Authenticated user with a role."""

    id: UUID
    email: str
    role: Role
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def can(self, permission: Permission) -> bool:
        """Return True if this user's role grants the given permission."""
        return permission in _ROLE_PERMISSIONS.get(self.role, frozenset())


@dataclass
class UserRegistration:
    """Value object carrying validated registration input.

    Hashing happens in infrastructure before this object is created —
    plaintext never crosses the domain boundary.
    """

    email: str
    hashed_password: str
    role: Role = Role.PROMOTOR

    def __post_init__(self) -> None:
        try:
            self.email = _validate_email_lib(
                self.email, check_deliverability=False
            ).normalized
        except EmailNotValidError as exc:
            raise ValueError(f"Invalid email: {exc}") from exc
