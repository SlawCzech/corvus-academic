"""initial identity schema

Revision ID: 0001_identity
Revises:
Create Date: 2026-06-09 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_identity"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "identity"


def upgrade() -> None:
    """Create identity schema with users and login_events tables."""
    op.execute("CREATE SCHEMA IF NOT EXISTS identity")

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("api_key_encrypted", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=_SCHEMA,
    )

    op.create_table(
        "login_events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("success", sa.Boolean, nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=False),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=_SCHEMA,
    )

    op.create_index(
        "ix_identity_login_events_user_id",
        "login_events",
        ["user_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_identity_login_events_success",
        "login_events",
        ["success"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    """Drop login_events and users tables, then drop identity schema."""
    op.drop_index(
        "ix_identity_login_events_success", table_name="login_events", schema=_SCHEMA
    )
    op.drop_index(
        "ix_identity_login_events_user_id", table_name="login_events", schema=_SCHEMA
    )
    op.drop_table("login_events", schema=_SCHEMA)
    op.drop_table("users", schema=_SCHEMA)
    op.execute("DROP SCHEMA IF EXISTS identity")
