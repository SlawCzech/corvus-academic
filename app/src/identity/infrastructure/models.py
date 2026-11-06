"""SQLAlchemy 2.0 ORM models for the identity service.

All tables live in the ``identity`` PostgreSQL schema so this service's
data is physically isolated from other bounded contexts.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, Uuid, false
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.shared.orm_types import UtcDateTime

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
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    # The university whose guidelines a promoter sees first. A plain id: the
    # catalog is another context, and identity never imports it.
    home_university_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    # The password is a temporary one an admin set; the next login must
    # replace it before anything else.
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )


class UserApiKeyModel(Base):
    """One provider key of one user (BYOK), Fernet-encrypted.

    A row per provider, so a promoter can keep an Anthropic key and an OpenAI
    key side by side and choose between them per action.
    """

    __tablename__ = "user_api_keys"
    __table_args__ = {"schema": _SCHEMA}

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(f"{_SCHEMA}.users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    provider: Mapped[str] = mapped_column(String(50), primary_key=True)
    key_encrypted: Mapped[str] = mapped_column(String(500), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime(),
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
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class AccessRequestModel(Base):
    """A visitor's request for an account, pending admin action.

    Not a signup: no password, no role. An admin reads the email here and
    creates the real account through the existing user-management flow.
    """

    __tablename__ = "access_requests"
    __table_args__ = {"schema": _SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
