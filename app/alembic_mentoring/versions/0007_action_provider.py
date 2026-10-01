"""remember which provider an action ran on

Revision ID: 0007_mentoring
Revises: 0006_mentoring
Create Date: 2026-10-01 00:00:00.000000

A promoter can now hold a key per provider and pick one per action, so the
provider is no longer implied by "the key they have". The name is kept on
the action — never the key — because a review paused for the promoter must
resume on the account it started on. NULL means the self-hosted model.

Actions from before this column are NULL as well, whatever they ran on —
nothing recorded it. A review that was started on a key and is still paused
across this migration therefore resumes on the self-hosted model.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_mentoring"
down_revision: str | Sequence[str] | None = "0006_mentoring"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "mentoring"


def upgrade() -> None:
    """Add the provider column."""
    op.add_column(
        "agent_actions",
        sa.Column("provider", sa.String(50), nullable=True),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    """Drop it."""
    op.drop_column("agent_actions", "provider", schema=_SCHEMA)
