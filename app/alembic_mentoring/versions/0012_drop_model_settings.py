"""drop the admin's allowlist of local models

Revision ID: 0012_mentoring
Revises: 0011_mentoring
Create Date: 2026-11-03 00:00:00.000000

Every action runs on a provider's key (ADR 0022), so there is nothing left
for an admin to offer. The rows named Ollama tags; nothing reads them.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_mentoring"
down_revision: str | Sequence[str] | None = "0011_mentoring"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "mentoring"


def upgrade() -> None:
    """Drop `model_settings`."""
    op.drop_index(
        "uq_mentoring_model_settings_default",
        table_name="model_settings",
        schema=_SCHEMA,
    )
    op.drop_table("model_settings", schema=_SCHEMA)


def downgrade() -> None:
    """Recreate an empty `model_settings`, as 0005 made it."""
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
