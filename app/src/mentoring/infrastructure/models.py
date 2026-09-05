"""SQLAlchemy 2.0 ORM models for the mentoring bounded context.

All tables live in the ``mentoring`` PostgreSQL schema, separate from
``identity`` — one schema per bounded context, migrated by its own Alembic
lineage (``alembic_mentoring/``).

Cross-context columns (``promotor_id``, ``uploaded_by``) are plain UUIDs with
no foreign key: they point at ``identity.users``, and contexts are not joined
across the boundary. Inside ``mentoring`` real foreign keys are used — it is
one context, one schema, one migration lineage.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON

_SCHEMA = "mentoring"

# JSONB on Postgres, plain JSON on SQLite (test engine) — same pattern as
# agent's AnalysisModel.result.
_JSON = JSONB().with_variant(JSON(), "sqlite")


class Base(DeclarativeBase):
    """Shared declarative base for all mentoring ORM models."""


class StudentModel(Base):
    """A student supervised by one promoter."""

    __tablename__ = "students"
    __table_args__ = (
        Index("ix_mentoring_students_promotor_id", "promotor_id"),
        {"schema": _SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    promotor_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    index_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    field_of_study: Mapped[str] = mapped_column(String(255), nullable=False)
    thesis_type: Mapped[str] = mapped_column(String(50), nullable=False)
    current_topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_topic_set_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class ThesisDraftModel(Base):
    """One uploaded version of a student's thesis, with extracted text.

    Unused until Phase 3, when `POST /students/{id}/drafts` calls the
    in-process extractor; the table ships now so the schema has one migration.
    """

    __tablename__ = "thesis_drafts"
    __table_args__ = (
        UniqueConstraint(
            "student_id", "version_number", name="uq_mentoring_draft_version"
        ),
        {"schema": _SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(f"{_SCHEMA}.students.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    pages: Mapped[int] = mapped_column(Integer, nullable=False)
    format: Mapped[str] = mapped_column(String(10), nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class AgentActionModel(Base):
    """Log of one AI action run against a student.

    Generic on purpose: every action type shares the same
    trigger → dispatch → poll → structured output → accept lifecycle, and
    ``output`` is JSONB so prompt-shape churn in Phases 2-3 costs no migration.

    Unused until Phase 2; created now so the mentoring schema is built once.
    """

    __tablename__ = "agent_actions"
    __table_args__ = (
        Index(
            "ix_mentoring_agent_actions_student_type_created",
            "student_id",
            "action_type",
            "created_at",
        ),
        Index("ix_mentoring_agent_actions_task_id", "task_id"),
        {"schema": _SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(f"{_SCHEMA}.students.id", ondelete="CASCADE"),
        nullable=False,
    )
    promotor_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    # IDs only — never the assembled prompt context, which can be large and
    # is reproducible from the referenced rows.
    input_ref: Mapped[Any] = mapped_column(  # type: ignore[assignment]
        _JSON, nullable=True, default=None
    )
    output: Mapped[Any] = mapped_column(  # type: ignore[assignment]
        _JSON, nullable=True, default=None
    )
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class MeetingNoteModel(Base):
    """A supervision meeting note approved by the promoter."""

    __tablename__ = "meeting_notes"
    __table_args__ = (
        Index(
            "ix_mentoring_meeting_notes_student_occurred",
            "student_id",
            "occurred_at",
        ),
        {"schema": _SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(f"{_SCHEMA}.students.id", ondelete="CASCADE"),
        nullable=False,
    )
    promotor_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Provenance: set when the note was accepted from an AI draft (Phase 3).
    source_action_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(f"{_SCHEMA}.agent_actions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
