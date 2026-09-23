"""keep the original file of each thesis draft

Revision ID: 0002_mentoring
Revises: 0001_mentoring
Create Date: 2026-09-23 00:00:00.000000

Adds `draft_files` (the original PDF/DOCX, through the shared `FileStore` port)
and a nullable `file_id` on `thesis_drafts` — nullable because every version
uploaded before this has no file to point at. The hash and size live on the
draft itself so they survive the file being purged.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_mentoring"
down_revision: str | Sequence[str] | None = "0001_mentoring"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "mentoring"


def upgrade() -> None:
    """Create `draft_files` and point drafts at it."""
    op.create_table(
        "draft_files",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(255), nullable=False),
        sa.Column("size", sa.Integer, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("data", sa.LargeBinary, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=_SCHEMA,
    )
    op.add_column(
        "thesis_drafts",
        sa.Column(
            "file_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.draft_files.id", ondelete="SET NULL"),
            nullable=True,
        ),
        schema=_SCHEMA,
    )
    op.add_column(
        "thesis_drafts",
        sa.Column("file_sha256", sa.String(64), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        "thesis_drafts",
        sa.Column("file_size", sa.Integer, nullable=True),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    """Drop the file columns and table."""
    op.drop_column("thesis_drafts", "file_size", schema=_SCHEMA)
    op.drop_column("thesis_drafts", "file_sha256", schema=_SCHEMA)
    op.drop_column("thesis_drafts", "file_id", schema=_SCHEMA)
    op.drop_table("draft_files", schema=_SCHEMA)
