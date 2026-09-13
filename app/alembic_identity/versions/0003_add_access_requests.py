"""add access_requests table

Revision ID: 0003_access_requests
Revises: 0002_api_key_provider
Create Date: 2026-09-13 00:00:00.000000

There is no self-signup — accounts are created by an admin. This table is
the on-ramp: a visitor leaves an email, an admin sees it in the user
management screen and decides whether to create a real account.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_access_requests"
down_revision: str | Sequence[str] | None = "0002_api_key_provider"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "identity"


def upgrade() -> None:
    """Create the access_requests table."""
    op.create_table(
        "access_requests",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    """Drop the access_requests table."""
    op.drop_table("access_requests", schema=_SCHEMA)
