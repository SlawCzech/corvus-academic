"""SQLAlchemy ORM models for the agent service.

All tables live in the ``analysis`` PostgreSQL schema.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON

_SCHEMA = "analysis"


class Base(DeclarativeBase):
    """Shared declarative base for all agent ORM models."""


class AgentTaskModel(Base):
    """One dispatched AI task and its outcome.

    ``status`` and ``result`` are written by the worker as the task runs, so
    this row — not Celery's expiring Redis backend — is what the history is
    read from.

    ``user_id``, ``action_id`` and ``student_id`` are plain UUIDs with no FK:
    they point at rows owned by `app` (identity and mentoring), across a
    service boundary.
    """

    __tablename__ = "agent_tasks"
    __table_args__ = {"schema": _SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    # Correlation with mentoring.agent_actions / mentoring.students.
    action_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True, index=True
    )
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    result: Mapped[Any] = mapped_column(  # type: ignore[assignment]
        JSONB().with_variant(JSON(), "sqlite"), nullable=True, default=None
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # An `ActionErrorCode` when the promoter can act on the failure (top up
    # the account, fix the key); None for everything else.
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # {"steps": [node, ...], "done": [node, ...]} while the graph runs; the
    # worker rewrites it after every node. Kept once the task ends, so a
    # failed run still shows how far it got.
    progress: Mapped[Any] = mapped_column(  # type: ignore[assignment]
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


class GuidelineChunkModel(Base):
    """One retrievable piece of a university requirements document.

    The embedding column is deliberately dimensionless (`vector`, not
    `vector(768)`): the embedding model is a setting, and pinning its
    dimension into the schema would make swapping it a migration. At this
    corpus size — tens of chunks per thesis type — an exact scan is both
    instant and more accurate than an approximate index; add HNSW, and a
    fixed dimension with it, when the corpus stops being small.
    """

    __tablename__ = "guideline_chunks"
    __table_args__ = (
        Index(
            "ix_analysis_guideline_chunks_lookup",
            "thesis_type",
            "embedding_model",
        ),
        {"schema": _SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    thesis_type: Mapped[str] = mapped_column(String(50), nullable=False)
    section: Mapped[str] = mapped_column(String(255), nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Which model produced the vector, and how wide it is. Both are recorded
    # so a stale row from a different model can never join a result set.
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[Any] = mapped_column(  # type: ignore[assignment]
        Vector().with_variant(JSON(), "sqlite"), nullable=False
    )
    # Rules the model must always see — how severities are decided, say —
    # regardless of what the similarity search turns up. A normative document
    # loses its meaning if retrieval quietly drops the part that defines the
    # judgement.
    always_include: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
