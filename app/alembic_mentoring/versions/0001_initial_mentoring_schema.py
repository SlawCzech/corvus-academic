"""initial mentoring schema

Revision ID: 0001_mentoring
Revises:
Create Date: 2026-09-05 00:00:00.000000

Creates all four mentoring tables in one migration, including the two
(`thesis_drafts`, `agent_actions`) not written to until Phases 2-3: the schema
is designed as a whole, so it is built as a whole.

Cross-context columns (`promotor_id`, `uploaded_by`) carry no foreign key —
they reference `identity.users` across a bounded-context boundary.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_mentoring"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "mentoring"


def upgrade() -> None:
    """Create the mentoring schema with its four tables."""
    op.execute("CREATE SCHEMA IF NOT EXISTS mentoring")

    op.create_table(
        "students",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("promotor_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("index_number", sa.String(50), nullable=True),
        sa.Column("field_of_study", sa.String(255), nullable=False),
        sa.Column("thesis_type", sa.String(50), nullable=False),
        sa.Column("current_topic", sa.Text, nullable=True),
        sa.Column("current_topic_set_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status", sa.String(50), nullable=False, server_default=sa.text("'active'")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_mentoring_students_promotor_id",
        "students",
        ["promotor_id"],
        schema=_SCHEMA,
    )

    op.create_table(
        "agent_actions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "student_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.students.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("promotor_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("task_id", sa.String(255), nullable=True),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column("input_ref", postgresql.JSONB(), nullable=True),
        sa.Column("output", postgresql.JSONB(), nullable=True),
        sa.Column(
            "accepted",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_mentoring_agent_actions_student_type_created",
        "agent_actions",
        ["student_id", "action_type", "created_at"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_mentoring_agent_actions_task_id",
        "agent_actions",
        ["task_id"],
        schema=_SCHEMA,
    )

    op.create_table(
        "thesis_drafts",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "student_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.students.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("pages", sa.Integer, nullable=False),
        sa.Column("format", sa.String(10), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "student_id", "version_number", name="uq_mentoring_draft_version"
        ),
        schema=_SCHEMA,
    )

    op.create_table(
        "meeting_notes",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "student_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.students.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("promotor_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "source_action_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.agent_actions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_mentoring_meeting_notes_student_occurred",
        "meeting_notes",
        ["student_id", "occurred_at"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    """Drop every mentoring table, then the schema itself."""
    op.drop_index(
        "ix_mentoring_meeting_notes_student_occurred",
        table_name="meeting_notes",
        schema=_SCHEMA,
    )
    op.drop_table("meeting_notes", schema=_SCHEMA)
    op.drop_table("thesis_drafts", schema=_SCHEMA)
    op.drop_index(
        "ix_mentoring_agent_actions_task_id",
        table_name="agent_actions",
        schema=_SCHEMA,
    )
    op.drop_index(
        "ix_mentoring_agent_actions_student_type_created",
        table_name="agent_actions",
        schema=_SCHEMA,
    )
    op.drop_table("agent_actions", schema=_SCHEMA)
    op.drop_index(
        "ix_mentoring_students_promotor_id", table_name="students", schema=_SCHEMA
    )
    op.drop_table("students", schema=_SCHEMA)
    op.execute("DROP SCHEMA IF EXISTS mentoring")
