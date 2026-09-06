"""store university requirements as retrievable embedded chunks

Revision ID: 0004_guideline_chunks
Revises: 0003_drop_legacy
Create Date: 2026-09-06 00:00:00.000000

Until now every requirements check pasted a whole requirements document into
the prompt. This table holds the same documents split into sections, each with
its embedding, so an action can be given the parts that bear on the thesis in
front of it.

The embedding column has no fixed dimension on purpose — the embedding model
is a setting, and each row records which model produced it, so switching
models is a re-ingest rather than a migration.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "0004_guideline_chunks"
down_revision: str | Sequence[str] | None = "0003_drop_legacy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "analysis"


def upgrade() -> None:
    """Create the pgvector extension and the guideline_chunks table."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

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


def downgrade() -> None:
    """Drop the table. The extension is left in place — it may be shared."""
    op.drop_index(
        "ix_analysis_guideline_chunks_lookup",
        table_name="guideline_chunks",
        schema=_SCHEMA,
    )
    op.drop_table("guideline_chunks", schema=_SCHEMA)
