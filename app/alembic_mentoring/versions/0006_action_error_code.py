"""keep the agent's code for a failure the promoter can act on

Revision ID: 0006_mentoring
Revises: 0005_mentoring
Create Date: 2026-09-30 00:00:00.000000

Copied from the agent on every refresh, next to the free-text `error`: no
credits on the provider account, a refused key, a rate limit that outlasted
the retries. The frontend turns the code into advice. Nullable: every other
failure, and every action from before this column, has none.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_mentoring"
down_revision: str | Sequence[str] | None = "0005_mentoring"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "mentoring"


def upgrade() -> None:
    """Add the error_code column."""
    op.add_column(
        "agent_actions",
        sa.Column("error_code", sa.String(50), nullable=True),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    """Drop it — the free-text error stays."""
    op.drop_column("agent_actions", "error_code", schema=_SCHEMA)
