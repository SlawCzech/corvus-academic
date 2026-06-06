"""add CASCADE delete on analyses.user_id and FK on login_events.user_id

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-06 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | Sequence[str] | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Replace plain FK on analyses.user_id with CASCADE delete.
    Add proper FK (SET NULL on delete) on login_events.user_id.
    """
    # --- analyses.user_id: drop old FK, recreate with ON DELETE CASCADE ---
    with op.batch_alter_table("analyses") as batch_op:
        # SQLite-safe: batch mode rewrites the table
        batch_op.drop_constraint("analyses_user_id_fkey", type_="foreignkey")
        batch_op.create_foreign_key(
            "analyses_user_id_fkey",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    # --- login_events.user_id: add FK with SET NULL on delete ---
    with op.batch_alter_table("login_events") as batch_op:
        batch_op.create_foreign_key(
            "login_events_user_id_fkey",
            "users",
            ["user_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    """Revert FK changes."""
    with op.batch_alter_table("login_events") as batch_op:
        batch_op.drop_constraint("login_events_user_id_fkey", type_="foreignkey")

    with op.batch_alter_table("analyses") as batch_op:
        batch_op.drop_constraint("analyses_user_id_fkey", type_="foreignkey")
        batch_op.create_foreign_key(
            "analyses_user_id_fkey",
            "users",
            ["user_id"],
            ["id"],
        )
