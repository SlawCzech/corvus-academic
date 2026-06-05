"""add task_id to analyses

Revision ID: b2e3f4a5c6d7
Revises: a3f1c2d4e5b6
Create Date: 2026-06-05 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b2e3f4a5c6d7"
down_revision: str | Sequence[str] | None = "a3f1c2d4e5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add nullable task_id column with index to analyses table."""
    op.add_column(
        "analyses",
        sa.Column("task_id", sa.String(255), nullable=True),
    )
    op.create_index("ix_analyses_task_id", "analyses", ["task_id"])


def downgrade() -> None:
    """Remove task_id column and its index from analyses table."""
    op.drop_index("ix_analyses_task_id", table_name="analyses")
    op.drop_column("analyses", "task_id")
