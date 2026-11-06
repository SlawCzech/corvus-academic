"""a promoter's home university

Revision ID: 0005_home_university
Revises: 0004_user_api_keys
Create Date: 2026-11-06 00:00:00.000000

The university whose guideline sets a promoter sees first. A plain id with
no foreign key: the catalog lives in the `guidelines` schema, another
bounded context.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_home_university"
down_revision: str | Sequence[str] | None = "0004_user_api_keys"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "identity"


def upgrade() -> None:
    """Add home_university_id to users."""
    op.add_column(
        "users",
        sa.Column("home_university_id", sa.Uuid(as_uuid=True), nullable=True),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    """Drop it."""
    op.drop_column("users", "home_university_id", schema=_SCHEMA)
