"""ORM models for the parts of a thesis and the fragments handed in for them.

Mirror ``domain/fragment.py``. A fragment's original upload is a row in
``draft_files``: same store, same blobs, one table for a context's files.
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.mentoring.infrastructure.orm.base import SCHEMA, Base


class ThesisPartModel(Base):
    """A part of the thesis, named by the promoter."""

    __tablename__ = "thesis_parts"
    __table_args__ = (
        Index("ix_mentoring_thesis_parts_due_on", "due_on"),
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
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


# Outside the class: an expression index needs the mapped column.
Index(
    "uq_mentoring_thesis_part_name",
    ThesisPartModel.student_id,
    func.lower(ThesisPartModel.name),
    unique=True,
)


class ThesisFragmentModel(Base):
    """One round of a part."""

    __tablename__ = "thesis_fragments"
    __table_args__ = (
        UniqueConstraint("part_id", "round_number", name="uq_mentoring_fragment_round"),
        Index(
            "ix_mentoring_thesis_fragments_awaiting",
            "student_id",
            postgresql_where=text("verdict IS NULL"),
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
    part_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(f"{SCHEMA}.thesis_parts.id", ondelete="CASCADE"),
        nullable=False,
    )
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    received_on: Mapped[date] = mapped_column(Date, nullable=False)
    question: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Null once purged under retention; the row itself is kept.
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    format: Mapped[str] = mapped_column(String(10), nullable=False)
    # Null for pasted text.
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(f"{SCHEMA}.draft_files.id", ondelete="SET NULL"),
        nullable=True,
    )
    file_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    purged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_action_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(f"{SCHEMA}.agent_actions.id", ondelete="SET NULL"),
        nullable=True,
    )
    verdict: Mapped[str | None] = mapped_column(String(20), nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    feedback_source_action_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(f"{SCHEMA}.agent_actions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
