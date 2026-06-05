"""add login_events table — admin seed moved to scripts/seed_admin.py

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-05 10:10:00.000000

"""

from collections.abc import Sequence

revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op: schema changes are in c3d4e5f6a7b8; seed moved to scripts/seed_admin.py."""


def downgrade() -> None:
    """No-op."""
