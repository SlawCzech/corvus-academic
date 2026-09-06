"""store which provider a user's API key belongs to

Revision ID: 0002_api_key_provider
Revises: 0001_identity
Create Date: 2026-09-06 00:00:00.000000

BYOK becomes real in Phase 4: the key was already stored encrypted, but the
provider it belongs to was only ever logged, so nothing could decide whether
to call Anthropic or OpenAI with it.

Existing rows keep a NULL provider — a key with no provider is not usable and
its owner is asked to set it again.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_api_key_provider"
down_revision: str | Sequence[str] | None = "0001_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "identity"


def upgrade() -> None:
    """Add the provider column next to the encrypted key."""
    op.add_column(
        "users",
        sa.Column("api_key_provider", sa.String(50), nullable=True),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    """Drop the provider column."""
    op.drop_column("users", "api_key_provider", schema=_SCHEMA)
