"""SQLAlchemy ORM models for the agent service.

All tables live in the ``analysis`` PostgreSQL schema.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON

_SCHEMA = "analysis"


class Base(DeclarativeBase):
    """Shared declarative base for all agent ORM models."""


class AnalysisModel(Base):
    """Persisted analysis task record.

    ``user_id`` is a plain UUID — no FK to identity.users (cross-service boundary).
    """

    __tablename__ = "analyses"
    __table_args__ = {"schema": _SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    evaluation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    task_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    result: Mapped[Any] = mapped_column(  # type: ignore[assignment]
        JSONB().with_variant(JSON(), "sqlite"), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
