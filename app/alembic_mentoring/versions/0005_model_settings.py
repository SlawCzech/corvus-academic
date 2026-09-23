"""the admin's allowlist of local models

Revision ID: 0005_mentoring
Revises: 0004_mentoring
Create Date: 2026-09-23 00:00:04.000000

Starts empty on purpose: with no rows, the agent's OLLAMA_MODEL is the only
model on offer, which is exactly what ran before this table existed.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_mentoring"
down_revision: str | Sequence[str] | None = "0004_mentoring"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "mentoring"


def upgrade() -> None:
    """Create `model_settings` with at most one default."""
    op.create_table(
        "model_settings",
        sa.Column("name", sa.String(200), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("updated_by", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )
    op.create_index(
        "uq_mentoring_model_settings_default",
        "model_settings",
        ["is_default"],
        unique=True,
        schema=_SCHEMA,
        postgresql_where=sa.text("is_default"),
    )


def downgrade() -> None:
    """Drop `model_settings`."""
    op.drop_index(
        "uq_mentoring_model_settings_default",
        table_name="model_settings",
        schema=_SCHEMA,
    )
    op.drop_table("model_settings", schema=_SCHEMA)
