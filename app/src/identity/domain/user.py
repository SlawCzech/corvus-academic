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
    SUBMIT_ANALYSIS = "submit_analysis"
    MANAGE_STUDENTS = "manage_students"
    MANAGE_GUIDELINES = "manage_guidelines"
    # Keep one's own provider keys: a promoter for actions, an admin for
    # rubrics drafted from a regulation (ADR 0025).
    HOLD_PROVIDER_KEYS = "hold_provider_keys"


# Two roles that do not overlap: an admin runs the platform (accounts, the
# guideline catalog), a promoter supervises
# students. An admin who also supervises uses a second, promoter account —
# students and their theses are not the admin's to see.
_ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(
        {
            Permission.MANAGE_USERS,
            Permission.MANAGE_GUIDELINES,
            Permission.HOLD_PROVIDER_KEYS,
        }
    ),
    Role.PROMOTOR: frozenset(
        {
            Permission.SUBMIT_ANALYSIS,
            Permission.MANAGE_STUDENTS,
            Permission.HOLD_PROVIDER_KEYS,
        }
    ),
}


@dataclass(frozen=True)
class User:
    """Authenticated user with a role."""

    id: UUID
    email: str
    role: Role
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    # Set when an admin hands out a temporary password: until the user picks
    # their own, the only thing their session can do is change it.
    must_change_password: bool = False

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
