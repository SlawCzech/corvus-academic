"""SQLAlchemy models for the guideline catalog, in the ``guidelines`` schema.

One schema and one Alembic lineage (``alembic_guidelines/``) for this bounded
context, like ``identity`` and ``mentoring``. ``created_by``/``published_by``
point at ``identity.users`` and carry no foreign key across the boundary.
"""

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.shared.orm_types import UtcDateTime
from src.shared.sql_file_store import FileBlobColumns

SCHEMA = "guidelines"

# JSONB on Postgres, plain JSON where tests run on SQLite.
_JSON = JSON().with_variant(postgresql.JSONB(), "postgresql")


class Base(DeclarativeBase):
    """Declarative base for the guideline catalog."""


class UniversityModel(Base):
    __tablename__ = "universities"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    short_name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)


class GuidelineSetModel(Base):
    __tablename__ = "guideline_sets"
    __table_args__ = (
        UniqueConstraint(
            "university_id", "thesis_type", "name", name="uq_guidelines_set_name"
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    university_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(f"{SCHEMA}.universities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    thesis_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class SourceFileModel(FileBlobColumns, Base):
    """The original regulation a version was read from."""

    __tablename__ = "source_files"
    __table_args__ = {"schema": SCHEMA}


class GuidelineVersionModel(Base):
    __tablename__ = "guideline_versions"
    __table_args__ = (
        UniqueConstraint("set_id", "version_no", name="uq_guidelines_version_no"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    set_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(f"{SCHEMA}.guideline_sets.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    rubric_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    thresholds: Mapped[dict[str, Any]] = mapped_column(_JSON, nullable=False)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(f"{SCHEMA}.source_files.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(), nullable=False, default=lambda: datetime.now(UTC)
    )
    published_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
