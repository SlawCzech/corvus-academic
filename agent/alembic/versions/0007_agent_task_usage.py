"""record the tokens each task spent

Revision ID: 0007_task_usage
Revises: 0006_task_error_code
Create Date: 2026-10-03 00:00:00.000000

`usage` is {input_tokens, output_tokens, total_tokens, by_model: {...}},
added to after every run under the task — a resumed review and a retry each
add what they spent. Nullable: a task from before this column, and one whose
model reported no usage, has none.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007_task_usage"
down_revision: str | Sequence[str] | None = "0006_task_error_code"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "analysis"


def upgrade() -> None:
    """Add the usage column."""
    op.add_column(
        "agent_tasks",
        sa.Column("usage", postgresql.JSONB(), nullable=True),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    """Drop it."""
    op.drop_column("agent_tasks", "usage", schema=_SCHEMA)
