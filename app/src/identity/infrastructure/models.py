"""SQLAlchemy 2.0 ORM models for the identity service.

All tables live in the ``identity`` PostgreSQL schema so this service's
data is physically isolated from other bounded contexts.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

_SCHEMA = "identity"


class Base(DeclarativeBase):
    """Shared declarative base for all identity ORM models."""


class UserModel(Base):
    """Persisted user record with hashed credentials."""

    __tablename__ = "users"
    __table_args__ = {"schema": _SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    # The user's own provider key (BYOK), Fernet-encrypted. The provider is
    # stored alongside it because a key alone does not say who to call.
    api_key_encrypted: Mapped[str | None] = mapped_column(
        String(500), nullable=True, default=None
    )
    api_key_provider: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class LoginEventModel(Base):
    """Audit log of login attempts."""

    __tablename__ = "login_events"
    __table_args__ = (
        Index("ix_identity_login_events_user_id", "user_id"),
        Index("ix_identity_login_events_success", "success"),
        {"schema": _SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
