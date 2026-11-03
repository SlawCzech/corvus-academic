"""ORM model for the AI action log.

Mirrors ``domain/action.py``.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from src.mentoring.infrastructure.orm.base import SCHEMA, Base
from src.shared.orm_types import UtcDateTime

# JSONB on Postgres, plain JSON on SQLite (test engine) — same pattern as
# agent's AnalysisModel.result. Only this table needs it, so it stays local
# rather than living in base.py for every model to see.
_JSON = JSONB().with_variant(JSON(), "sqlite")


class AgentActionModel(Base):
    """Log of one AI action run against a student.

    Generic on purpose: every action type shares the same
    trigger → dispatch → poll → structured output → accept lifecycle, and
    ``output`` is JSONB so prompt-shape churn costs no migration.
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
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The BYOK provider the run was sent to, or None for the self-hosted
    # model. The name only, never the key: a paused review resumes on it.
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # IDs only — never the assembled prompt context, which can be large and
    # is reproducible from the referenced rows.
    input_ref: Mapped[Any] = mapped_column(  # type: ignore[assignment]
        _JSON, nullable=True, default=None
    )
    output: Mapped[Any] = mapped_column(  # type: ignore[assignment]
        _JSON, nullable=True, default=None
    )
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    accepted_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The agent's code for a failure the promoter can act on; see the agent's
    # `ActionErrorCode`.
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Tokens the agent reports the action spent, totals and by model.
    usage: Mapped[Any] = mapped_column(  # type: ignore[assignment]
        _JSON, nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime(),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
