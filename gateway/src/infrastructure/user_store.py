"""In-memory user store — replaced by DB-backed repository in session 3.2."""

from dataclasses import dataclass
from uuid import UUID

import bcrypt
import structlog

from src.domain.user import Role, User

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@dataclass
class _UserRecord:
    user: User
    hashed_password: bytes


def _hash(plain: str) -> bytes:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt())


def _verify(plain: str, hashed: bytes) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed)


# Predefined users for development and testing — replaced by DB in session 3.2
_STORE: dict[str, _UserRecord] = {
    "admin@corvus.local": _UserRecord(
        user=User(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            email="admin@corvus.local",
            role=Role.ADMIN,
        ),
        hashed_password=_hash("admin-secret"),
    ),
    "promotor@corvus.local": _UserRecord(
        user=User(
            id=UUID("00000000-0000-0000-0000-000000000002"),
            email="promotor@corvus.local",
            role=Role.PROMOTOR,
        ),
        hashed_password=_hash("promotor-secret"),
    ),
}


def find_by_credentials(email: str, password: str) -> User | None:
    """Return User if credentials match a known record, otherwise None."""
    record = _STORE.get(email)
    if record is None:
        logger.warning("login_unknown_email", email=email)
        return None
    if not _verify(password, record.hashed_password):
        logger.warning("login_bad_password", email=email)
        return None
    return record.user
