"""keep the tokens each action spent

Revision ID: 0008_mentoring
Revises: 0007_mentoring
Create Date: 2026-10-03 00:00:00.000000

Copied from the agent on every refresh, like `error_code`:
{input_tokens, output_tokens, total_tokens, by_model: {...}}. On a hosted
model that is what the promoter's account was billed for. Nullable: an
action from before this column, and one whose model reported nothing, has
none.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_mentoring"
down_revision: str | Sequence[str] | None = "0007_mentoring"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "mentoring"


def upgrade() -> None:
    """Add the usage column."""
    op.add_column(
        "agent_actions",
        sa.Column("usage", postgresql.JSONB(), nullable=True),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    """Drop it."""
    op.drop_column("agent_actions", "usage", schema=_SCHEMA)
