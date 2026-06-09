"""migrate analyses to gateway schema, drop identity tables from gateway scope

Revision ID: f001_gateway_schema
Revises: e5f6a7b8c9d0
Create Date: 2026-06-09 00:00:00.000000

This migration marks the split of the gateway and identity bounded contexts:

1. Creates the ``gateway`` PostgreSQL schema.
2. Moves ``public.analyses`` into ``gateway.analyses``.
3. Drops the FK from analyses.user_id → users.id (cross-service boundary:
   users are now owned by the identity service, not the gateway).
4. Drops ``public.users`` and ``public.login_events`` — these tables are now
   owned and managed by the identity service's own Alembic chain.
   The identity service will recreate them under ``identity.*``.

On a fresh database: run identity migrations first, then gateway migrations.
On an existing database: user data must be migrated to identity.users before
running this migration (see docs/sessions.md for the data migration guide).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "f001_gateway_schema"
down_revision: str | Sequence[str] | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_SCHEMA = "public"
_NEW_SCHEMA = "gateway"


def upgrade() -> None:
    """Create gateway schema, migrate analyses, drop identity tables."""
    # 1. Create the gateway schema.
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_NEW_SCHEMA}")

    # 2. Drop the FK from analyses.user_id → public.users.id before moving.
    with op.batch_alter_table("analyses", schema=_OLD_SCHEMA) as batch_op:
        batch_op.drop_constraint("analyses_user_id_fkey", type_="foreignkey")

    # 3. Move analyses table into the gateway schema.
    op.execute(f"ALTER TABLE {_OLD_SCHEMA}.analyses SET SCHEMA {_NEW_SCHEMA}")

    # 4. Drop public.login_events (owned by identity service going forward).
    op.execute("DROP TABLE IF EXISTS public.login_events")

    # 5. Drop public.users (owned by identity service going forward).
    op.execute("DROP TABLE IF EXISTS public.users")


def downgrade() -> None:
    """Reverse: move analyses back to public, recreate users placeholder."""
    # Restore analyses to public schema.
    op.execute(f"ALTER TABLE {_NEW_SCHEMA}.analyses SET SCHEMA {_OLD_SCHEMA}")

    # Recreate a minimal users table so the FK can be added back.
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=_OLD_SCHEMA,
    )

    # Restore FK.
    with op.batch_alter_table("analyses", schema=_OLD_SCHEMA) as batch_op:
        batch_op.create_foreign_key(
            "analyses_user_id_fkey",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    op.execute(f"DROP SCHEMA IF EXISTS {_NEW_SCHEMA}")
