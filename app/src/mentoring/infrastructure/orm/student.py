"""ORM models for a student and their meeting notes.

Mirrors ``domain/student.py``: the same two entities live together here for
the same reason they live together there.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.mentoring.infrastructure.orm.base import SCHEMA, Base


class StudentModel(Base):
    """A student supervised by one promoter."""

    __tablename__ = "students"
    __table_args__ = (
        Index("ix_mentoring_students_promotor_id", "promotor_id"),
        {"schema": SCHEMA},
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
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # No foreign key: thesis_drafts already points here, and a cycle between
    # the two tables buys nothing the service does not already check.
    accepted_draft_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    draft_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(f"{SCHEMA}.students.id", ondelete="CASCADE"),
        nullable=False,
    )
    promotor_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Provenance: set when the note started life as an accepted AI draft.
    source_action_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(f"{SCHEMA}.agent_actions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
