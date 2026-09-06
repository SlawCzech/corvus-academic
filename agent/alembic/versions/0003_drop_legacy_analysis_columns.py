"""drop the legacy /analysis correlation column

Revision ID: 0003_drop_legacy
Revises: 0002_agent_tasks
Create Date: 2026-09-06 00:00:00.000000

`POST /analysis` and the `analyze_thesis` task are gone: every task now runs
for a mentoring action, correlated by `action_id`. `evaluation_id` was the id
the pre-mentoring frontend generated per upload and has no meaning left.

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_drop_legacy"
down_revision: str | Sequence[str] | None = "0002_agent_tasks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "analysis"


def upgrade() -> None:
    """Drop evaluation_id."""
    op.drop_column("agent_tasks", "evaluation_id", schema=_SCHEMA)


def downgrade() -> None:
    """Restore the column, empty — the ids themselves are not recoverable."""
    op.add_column(
        "agent_tasks",
        sa.Column("evaluation_id", sa.String(255), nullable=True),
        schema=_SCHEMA,
    )
