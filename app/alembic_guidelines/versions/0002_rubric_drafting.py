"""a rubric drafted from the regulation

Revision ID: 0002_guidelines
Revises: 0001_guidelines
Create Date: 2026-11-06 00:00:00.000000

A draft version remembers the agent's task drafting its rubric from the
attached regulation, why the last attempt failed, and what the model asks
the admin to check (ADR 0025).

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_guidelines"
down_revision: str | Sequence[str] | None = "0001_guidelines"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "guidelines"


def upgrade() -> None:
    """Add the drafting task and its last error to guideline versions."""
    op.add_column(
        "guideline_versions",
        sa.Column("drafting_task_id", sa.String(64), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        "guideline_versions",
        sa.Column("drafting_error", sa.Text(), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        "guideline_versions",
        sa.Column("draft_notes", postgresql.JSONB(), nullable=True),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    """Drop the three columns."""
    op.drop_column("guideline_versions", "draft_notes", schema=_SCHEMA)
    op.drop_column("guideline_versions", "drafting_error", schema=_SCHEMA)
    op.drop_column("guideline_versions", "drafting_task_id", schema=_SCHEMA)
