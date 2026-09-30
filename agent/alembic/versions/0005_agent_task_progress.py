"""record which graph nodes a running task has finished

Revision ID: 0005_task_progress
Revises: 0004_guideline_chunks
Create Date: 2026-09-30 00:00:00.000000

A review runs for ten minutes and more on a local model. `progress` holds the
graph's steps and the ones already done, written by the worker after each
node, so the action panel can show where a run is instead of a spinner.
Nullable: tasks from before this column, and tasks not yet started, have none.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005_task_progress"
down_revision: str | Sequence[str] | None = "0004_guideline_chunks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "analysis"


def upgrade() -> None:
    """Add the progress column."""
    op.add_column(
        "agent_tasks",
        sa.Column("progress", postgresql.JSONB(), nullable=True),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    """Drop it — progress is transient; nothing is lost that matters."""
    op.drop_column("agent_tasks", "progress", schema=_SCHEMA)
