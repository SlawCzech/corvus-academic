"""record why a task failed, when the promoter can act on it

Revision ID: 0006_task_error_code
Revises: 0005_task_progress
Create Date: 2026-09-30 00:00:01.000000

`error` holds whatever the provider said, in its words. `error_code` names
the few failures the promoter can fix themselves — no credits on the
account, a refused key, a rate limit that outlasted the retries — so the
frontend can say what to do instead of showing a JSON blob. Nullable: every
other failure, and every task from before this column, has none.

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_task_error_code"
down_revision: str | Sequence[str] | None = "0005_task_progress"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "analysis"


def upgrade() -> None:
    """Add the error_code column."""
    op.add_column(
        "agent_tasks",
        sa.Column("error_code", sa.String(50), nullable=True),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    """Drop it — the free-text error stays."""
    op.drop_column("agent_tasks", "error_code", schema=_SCHEMA)
