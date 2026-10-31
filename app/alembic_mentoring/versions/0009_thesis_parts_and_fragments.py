"""parts of a thesis, and the fragments handed in for them

Revision ID: 0009_mentoring
Revises: 0008_mentoring
Create Date: 2026-10-31 00:00:00.000000

Fragments are their own table, not a kind of `thesis_drafts`: the actions read
"the latest version", and a chapter must never become that (ADR 0014). Their
files go to `draft_files`, the context's one file table.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_mentoring"
down_revision: str | Sequence[str] | None = "0008_mentoring"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "mentoring"


def upgrade() -> None:
    """Create the two tables."""
    op.create_table(
        "thesis_parts",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "student_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.students.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("due_on", sa.Date, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )
    op.create_index(
        "uq_mentoring_thesis_part_name",
        "thesis_parts",
        ["student_id", sa.text("lower(name)")],
        unique=True,
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_mentoring_thesis_parts_due_on", "thesis_parts", ["due_on"], schema=_SCHEMA
    )

    op.create_table(
        "thesis_fragments",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "student_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.students.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "part_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.thesis_parts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("round_number", sa.Integer, nullable=False),
        sa.Column("received_on", sa.Date, nullable=False),
        sa.Column("question", sa.Text, nullable=True),
        sa.Column("text", sa.Text, nullable=True),
        sa.Column("char_count", sa.Integer, nullable=False),
        sa.Column("pages", sa.Integer, nullable=False),
        sa.Column("format", sa.String(10), nullable=False),
        sa.Column("filename", sa.String(255), nullable=True),
        sa.Column("uploaded_by", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "file_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.draft_files.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("file_sha256", sa.String(64), nullable=True),
        sa.Column("file_size", sa.Integer, nullable=True),
        sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "review_action_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.agent_actions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("verdict", sa.String(20), nullable=True),
        sa.Column("feedback", sa.Text, nullable=True),
        sa.Column("feedback_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "feedback_source_action_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.agent_actions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "part_id", "round_number", name="uq_mentoring_fragment_round"
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_mentoring_thesis_fragments_awaiting",
        "thesis_fragments",
        ["student_id"],
        postgresql_where=sa.text("verdict IS NULL"),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    """Drop them. Files of fragments stay in `draft_files`, unreferenced."""
    op.drop_table("thesis_fragments", schema=_SCHEMA)
    op.drop_table("thesis_parts", schema=_SCHEMA)
