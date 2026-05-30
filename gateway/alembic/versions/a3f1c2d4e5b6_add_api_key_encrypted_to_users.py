"""add api_key_encrypted to users

Revision ID: a3f1c2d4e5b6
Revises: efb1f4b4b498
Create Date: 2026-05-30 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a3f1c2d4e5b6"
down_revision: str | Sequence[str] | None = "efb1f4b4b498"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add encrypted API key column to users table."""
    op.add_column(
        "users",
        sa.Column("api_key_encrypted", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    """Remove encrypted API key column from users table."""
    op.drop_column("users", "api_key_encrypted")
