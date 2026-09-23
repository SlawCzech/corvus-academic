"""the guideline set a student's thesis is judged against

Revision ID: 0004_mentoring
Revises: 0003_mentoring
Create Date: 2026-09-23 00:00:03.000000

A plain UUID into `guidelines.guideline_sets` — another bounded context, so no
foreign key. Null means the agent's own requirements for the thesis type.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_mentoring"
down_revision: str | Sequence[str] | None = "0003_mentoring"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "mentoring"


def upgrade() -> None:
    """Add `students.guideline_set_id`."""
    op.add_column(
        "students",
        sa.Column("guideline_set_id", sa.Uuid(as_uuid=True), nullable=True),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    """Drop `students.guideline_set_id`."""
    op.drop_column("students", "guideline_set_id", schema=_SCHEMA)
