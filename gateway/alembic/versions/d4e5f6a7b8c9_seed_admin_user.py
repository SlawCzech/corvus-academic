"""seed admin user

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-05 10:10:00.000000

"""

import os
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Insert default admin user if not already present.

    Reads ADMIN_EMAIL and ADMIN_PASSWORD from environment variables.
    Skips silently if admin already exists — safe to run multiple times.
    """
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@corvus.local")
    admin_password = os.environ.get("ADMIN_PASSWORD", "")

    if not admin_password:
        # No password configured — skip seed to avoid creating a locked-out admin.
        return

    import bcrypt

    hashed = bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt()).decode()

    conn = op.get_bind()
    existing = conn.execute(
        sa.text("SELECT id FROM users WHERE email = :email"),
        {"email": admin_email},
    ).fetchone()

    if existing is not None:
        return

    conn.execute(
        sa.text(
            "INSERT INTO users (id, email, role, hashed_password, created_at)"
            " VALUES (:id, :email, :role, :hashed_password, :created_at)"
        ),
        {
            "id": str(uuid.uuid4()),
            "email": admin_email,
            "role": "admin",
            "hashed_password": hashed,
            "created_at": datetime.now(UTC),
        },
    )


def downgrade() -> None:
    """Remove the seeded admin user if it still exists."""
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@corvus.local")
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM users WHERE email = :email AND role = 'admin'"),
        {"email": admin_email},
    )
