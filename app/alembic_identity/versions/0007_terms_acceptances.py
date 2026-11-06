"""terms of service acceptances

Revision ID: 0007_terms_acceptances
Revises: 0006_must_change_password
Create Date: 2026-11-06 00:00:00.000000

A promoter accepts the terms of service, which carry the data processing
agreement, before working with student data. A row per user and version:
the record of who accepted which text, and when.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_terms_acceptances"
down_revision: str | Sequence[str] | None = "0006_must_change_password"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "identity"


def upgrade() -> None:
    """Create terms_acceptances."""
    op.create_table(
        "terms_acceptances",
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("version", sa.String(20), primary_key=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    """Drop it."""
    op.drop_table("terms_acceptances", schema=_SCHEMA)
