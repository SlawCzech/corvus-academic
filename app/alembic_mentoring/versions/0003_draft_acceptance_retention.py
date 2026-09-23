"""accept a final draft; purge versions under retention

Revision ID: 0003_mentoring
Revises: 0002_mentoring
Create Date: 2026-09-23 00:00:01.000000

`students` gains the acceptance (`accepted_draft_id`, `draft_accepted_at`) and
the moment supervision ended (`closed_at`), backfilled from `updated_at` for
students already graduated or archived — the best record there is of when
that happened. `thesis_drafts.text` becomes nullable (a purged version keeps
its row), gains `purged_at`, and stores its length so a purged version still
reports it.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_mentoring"
down_revision: str | Sequence[str] | None = "0002_mentoring"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "mentoring"


def upgrade() -> None:
    """Add acceptance and retention columns, and backfill them."""
    op.add_column(
        "students",
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        "students",
        sa.Column("accepted_draft_id", sa.Uuid(as_uuid=True), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        "students",
        sa.Column("draft_accepted_at", sa.DateTime(timezone=True), nullable=True),
        schema=_SCHEMA,
    )
    op.execute(
        "UPDATE mentoring.students SET closed_at = updated_at "
        "WHERE status IN ('graduated', 'archived')"
    )

    op.alter_column("thesis_drafts", "text", nullable=True, schema=_SCHEMA)
    op.add_column(
        "thesis_drafts",
        sa.Column(
            "char_count", sa.Integer, nullable=False, server_default=sa.text("0")
        ),
        schema=_SCHEMA,
    )
    op.execute("UPDATE mentoring.thesis_drafts SET char_count = length(text)")
    op.add_column(
        "thesis_drafts",
        sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    """Drop the columns. Purged versions cannot get their text back."""
    op.drop_column("thesis_drafts", "purged_at", schema=_SCHEMA)
    op.drop_column("thesis_drafts", "char_count", schema=_SCHEMA)
    op.execute("UPDATE mentoring.thesis_drafts SET text = '' WHERE text IS NULL")
    op.alter_column("thesis_drafts", "text", nullable=False, schema=_SCHEMA)
    op.drop_column("students", "draft_accepted_at", schema=_SCHEMA)
    op.drop_column("students", "accepted_draft_id", schema=_SCHEMA)
    op.drop_column("students", "closed_at", schema=_SCHEMA)
