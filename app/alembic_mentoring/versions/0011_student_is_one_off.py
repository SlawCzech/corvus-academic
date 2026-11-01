"""one-off reviews

Revision ID: 0011_mentoring
Revises: 0010_mentoring
Create Date: 2026-11-01 00:00:00.000000

A thesis reviewed once, with nobody to supervise, is a hidden student: see
ADR 0017. Every existing row is a real student.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_mentoring"
down_revision: str | Sequence[str] | None = "0010_mentoring"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "mentoring"


def upgrade() -> None:
    """Add the flag."""
    op.add_column(
        "students",
        sa.Column(
            "is_one_off", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    """Drop it."""
    op.drop_column("students", "is_one_off", schema=_SCHEMA)
