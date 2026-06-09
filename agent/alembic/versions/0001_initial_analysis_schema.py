"""initial analysis schema

Revision ID: 0001_analysis
Revises:
Create Date: 2026-06-09 00:00:00.000000

Creates the ``analysis`` PostgreSQL schema and the ``analyses`` table.
user_id has no FK — user records live in the identity service.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0001_analysis"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "analysis"


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS analysis")

    op.create_table(
        "analyses",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("evaluation_id", sa.String(255), nullable=False),
        sa.Column("task_id", sa.String(255), nullable=True, index=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column(
            "result",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("analyses", schema=_SCHEMA)
    op.execute("DROP SCHEMA IF EXISTS analysis")
