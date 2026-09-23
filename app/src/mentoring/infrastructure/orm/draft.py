"""ORM models for one uploaded version of a student's thesis, and its file.

``ThesisDraftModel`` mirrors ``domain/draft.py``. ``DraftFileModel`` holds the
original upload through the shared ``FileStore`` port; the draft keeps the
file's hash and size itself, so they outlive the file when it is purged.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.mentoring.infrastructure.orm.base import SCHEMA, Base
from src.shared.sql_file_store import FileBlobColumns


class DraftFileModel(FileBlobColumns, Base):
    """The original PDF/DOCX a draft was extracted from."""

    __tablename__ = "draft_files"
    __table_args__ = {"schema": SCHEMA}


class ThesisDraftModel(Base):
    """One uploaded version of a student's thesis, with extracted text."""

    __tablename__ = "thesis_drafts"
    __table_args__ = (
        UniqueConstraint(
            "student_id", "version_number", name="uq_mentoring_draft_version"
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
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    pages: Mapped[int] = mapped_column(Integer, nullable=False)
    format: Mapped[str] = mapped_column(String(10), nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    # Null for versions uploaded before files were kept.
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(f"{SCHEMA}.draft_files.id", ondelete="SET NULL"),
        nullable=True,
    )
    file_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
