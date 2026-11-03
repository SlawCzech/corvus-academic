"""rename analyses to agent_tasks and make task status durable

Revision ID: 0002_agent_tasks
Revises: 0001_analysis
Create Date: 2026-09-05 00:00:00.000000

The table stops being about one kind of work ("analyses") and becomes the log
of every AI action the agent runs, with a status the worker writes as it goes
— previously status was set once to "PENDING" and the live value was read from
Celery's Redis backend, which expires.

Existing rows are legacy full analyses, so they are backfilled with
action_type='generate_review' and their status is normalised to the new
vocabulary (pending/running/completed/failed).

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_agent_tasks"
down_revision: str | Sequence[str] | None = "0001_analysis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "analysis"


def upgrade() -> None:
    """Rename the table, add action/correlation columns, normalise status."""
    op.rename_table("analyses", "agent_tasks", schema=_SCHEMA)

    op.add_column(
        "agent_tasks",
        sa.Column(
            "action_type",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'generate_review'"),
        ),
        schema=_SCHEMA,
    )
    op.add_column(
        "agent_tasks", sa.Column("error", sa.Text, nullable=True), schema=_SCHEMA
    )
    op.add_column(
        "agent_tasks",
        sa.Column("action_id", sa.Uuid(as_uuid=True), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        "agent_tasks",
        sa.Column("student_id", sa.Uuid(as_uuid=True), nullable=True),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_analysis_agent_tasks_action_id",
        "agent_tasks",
        ["action_id"],
        schema=_SCHEMA,
    )

    # Actions carry action_id instead; only the legacy flow sets this.
    op.alter_column("agent_tasks", "evaluation_id", nullable=True, schema=_SCHEMA)

    # Old vocabulary was Celery's ("PENDING" written once, never updated).
    op.execute(
        "UPDATE analysis.agent_tasks SET status = 'pending' "
        "WHERE status IN ('PENDING', 'STARTED', 'RETRY')"
    )
    op.execute(
        "UPDATE analysis.agent_tasks SET status = 'completed' WHERE status = 'SUCCESS'"
    )
    op.execute(
        "UPDATE analysis.agent_tasks SET status = 'failed' "
        "WHERE status IN ('FAILURE', 'REVOKED')"
    )


def downgrade() -> None:
    """Reverse the rename and drop the added columns."""
    op.execute(
        "UPDATE analysis.agent_tasks SET status = 'PENDING' "
        "WHERE status IN ('pending', 'running')"
    )
    op.execute(
        "UPDATE analysis.agent_tasks SET status = 'SUCCESS' WHERE status = 'completed'"
    )
    op.execute(
        "UPDATE analysis.agent_tasks SET status = 'FAILURE' WHERE status = 'failed'"
    )
    op.execute(
        "UPDATE analysis.agent_tasks SET evaluation_id = '' WHERE evaluation_id IS NULL"
    )
    op.alter_column("agent_tasks", "evaluation_id", nullable=False, schema=_SCHEMA)
    op.drop_index(
        "ix_analysis_agent_tasks_action_id", table_name="agent_tasks", schema=_SCHEMA
    )
    op.drop_column("agent_tasks", "student_id", schema=_SCHEMA)
    op.drop_column("agent_tasks", "action_id", schema=_SCHEMA)
    op.drop_column("agent_tasks", "error", schema=_SCHEMA)
    op.drop_column("agent_tasks", "action_type", schema=_SCHEMA)
    op.rename_table("agent_tasks", "analyses", schema=_SCHEMA)
