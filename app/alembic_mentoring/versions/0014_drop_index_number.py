"""drop students' index number

Revision ID: 0014_mentoring
Revises: 0013_mentoring
Create Date: 2026-11-06 00:00:00.000000

The second half of 0013: the code stopped reading the column and 0013
emptied it in the release before this one, which is live, so a rollback
from here lands on an image that never asks for it (ADR 0027).

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_mentoring"
down_revision: str | Sequence[str] | None = "0013_mentoring"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "mentoring"


def upgrade() -> None:
    """Drop the column."""
    op.drop_column("students", "index_number", schema=_SCHEMA)


def downgrade() -> None:
    """Bring the column back, empty, as 0013 left it."""
    op.add_column(
        "students",
        sa.Column("index_number", sa.String(50), nullable=True),
        schema=_SCHEMA,
    )
