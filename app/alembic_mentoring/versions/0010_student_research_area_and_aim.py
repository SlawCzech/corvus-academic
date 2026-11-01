"""what the promoter agreed with the student

Revision ID: 0010_mentoring
Revises: 0009_mentoring
Create Date: 2026-10-31 00:00:00.000000

Two optional fields the actions read as context: see ADR 0015. Nullable, so
no student needs them filled in.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_mentoring"
down_revision: str | Sequence[str] | None = "0009_mentoring"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "mentoring"


def upgrade() -> None:
    """Add the two columns."""
    op.add_column(
        "students",
        sa.Column("research_area", sa.String(255), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        "students",
        sa.Column("research_aim", sa.Text(), nullable=True),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    """Drop them."""
    op.drop_column("students", "research_aim", schema=_SCHEMA)
    op.drop_column("students", "research_area", schema=_SCHEMA)
