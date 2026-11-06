"""a temporary password the user must replace

Revision ID: 0006_must_change_password
Revises: 0005_home_university
Create Date: 2026-11-06 00:00:00.000000

An admin who resets a forgotten password hands out a temporary one; this
flag keeps the account limited to changing it until the user picks their
own. Every existing account starts without it.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_must_change_password"
down_revision: str | Sequence[str] | None = "0005_home_university"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "identity"


def upgrade() -> None:
    """Add must_change_password to users, false for everyone."""
    op.add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    """Drop it."""
    op.drop_column("users", "must_change_password", schema=_SCHEMA)
