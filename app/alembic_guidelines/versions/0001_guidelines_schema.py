"""guideline catalog schema

Revision ID: 0001_guidelines
Revises:
Create Date: 2026-09-23 00:00:02.000000

The `guidelines` bounded context: universities, their requirement sets per
thesis type, immutable versions of each, and the original regulation files.
`created_by`/`published_by` reference `identity.users` across a context
boundary and carry no foreign key.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_guidelines"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "guidelines"


def upgrade() -> None:
    """Create the guidelines schema and its four tables."""
    op.execute("CREATE SCHEMA IF NOT EXISTS guidelines")

    op.create_table(
        "universities",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("short_name", sa.String(50), nullable=False, unique=True),
        schema=_SCHEMA,
    )

    op.create_table(
        "guideline_sets",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "university_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.universities.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("thesis_type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.UniqueConstraint(
            "university_id", "thesis_type", "name", name="uq_guidelines_set_name"
        ),
        schema=_SCHEMA,
    )

    op.create_table(
        "source_files",
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

    op.create_table(
        "guideline_versions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "set_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.guideline_sets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_no", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("rubric_md", sa.Text, nullable=False, server_default=""),
        sa.Column("thresholds", postgresql.JSONB(), nullable=False),
        sa.Column("effective_from", sa.Date, nullable=True),
        sa.Column(
            "source_file_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.source_files.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_filename", sa.String(255), nullable=True),
        sa.Column("source_sha256", sa.String(64), nullable=True),
        sa.Column("source_size", sa.Integer, nullable=True),
        sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("published_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("set_id", "version_no", name="uq_guidelines_version_no"),
        schema=_SCHEMA,
    )
    # At most one version in force per set, enforced by the database too.
    op.create_index(
        "uq_guidelines_one_published_per_set",
        "guideline_versions",
        ["set_id"],
        unique=True,
        schema=_SCHEMA,
        postgresql_where=sa.text("status = 'published'"),
    )


def downgrade() -> None:
    """Drop every guidelines table.

    The schema stays: it also holds this lineage's own `alembic_version`
    table, which Alembic writes to after this function returns.
    """
    op.drop_index(
        "uq_guidelines_one_published_per_set",
        table_name="guideline_versions",
        schema=_SCHEMA,
    )
    op.drop_table("guideline_versions", schema=_SCHEMA)
    op.drop_table("source_files", schema=_SCHEMA)
    op.drop_table("guideline_sets", schema=_SCHEMA)
    op.drop_table("universities", schema=_SCHEMA)
