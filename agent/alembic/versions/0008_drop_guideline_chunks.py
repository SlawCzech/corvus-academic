"""drop guideline_chunks: requirements go into the prompt whole

Revision ID: 0008_drop_guideline_chunks
Revises: 0007_task_usage
Create Date: 2026-11-03 00:00:00.000000

Retrieval ran only for a student without a guideline set, over files of a
few kilobytes that a hosted model takes whole (ADR 0021). The extension is
left in place, as 0004's downgrade leaves it: dropping it buys nothing.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "0008_drop_guideline_chunks"
down_revision: str | Sequence[str] | None = "0007_task_usage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "analysis"


def upgrade() -> None:
    """Drop the table and its index."""
    op.drop_index(
        "ix_analysis_guideline_chunks_lookup",
        table_name="guideline_chunks",
        schema=_SCHEMA,
    )
    op.drop_table("guideline_chunks", schema=_SCHEMA)


def downgrade() -> None:
    """Recreate the empty table; the rows were derived and are re-ingestable."""
    op.create_table(
        "guideline_chunks",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("thesis_type", sa.String(50), nullable=False),
        sa.Column("section", sa.String(255), nullable=False),
        sa.Column("chunk_text", sa.Text, nullable=False),
        sa.Column("embedding_model", sa.String(100), nullable=False),
        sa.Column("dimensions", sa.Integer, nullable=False),
        sa.Column("embedding", Vector(), nullable=False),
        sa.Column(
            "always_include",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
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
        "ix_analysis_guideline_chunks_lookup",
        "guideline_chunks",
        ["thesis_type", "embedding_model"],
        schema=_SCHEMA,
    )
