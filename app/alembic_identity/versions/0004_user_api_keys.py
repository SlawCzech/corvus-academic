"""one key per provider instead of one key per user

Revision ID: 0004_user_api_keys
Revises: 0003_access_requests
Create Date: 2026-10-01 00:00:00.000000

A promoter could hold a single key: saving an OpenAI key overwrote the
Anthropic one. Keys move to their own table, a row per user and provider,
so both can be stored and one chosen per action.

Existing keys are carried over. A key whose provider was never recorded
(rows from before 0002) was unusable already and is dropped with the column.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_user_api_keys"
down_revision: str | Sequence[str] | None = "0003_access_requests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "identity"


def upgrade() -> None:
    """Create user_api_keys, move the stored keys into it, drop the columns."""
    op.create_table(
        "user_api_keys",
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("provider", sa.String(50), primary_key=True),
        sa.Column("key_encrypted", sa.String(500), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=_SCHEMA,
    )
    op.execute(
        f"""
        INSERT INTO {_SCHEMA}.user_api_keys (user_id, provider, key_encrypted)
        SELECT id, api_key_provider, api_key_encrypted
        FROM {_SCHEMA}.users
        WHERE api_key_encrypted IS NOT NULL AND api_key_provider IS NOT NULL
        """  # noqa: S608 — the schema name is a constant, not input
    )
    op.drop_column("users", "api_key_provider", schema=_SCHEMA)
    op.drop_column("users", "api_key_encrypted", schema=_SCHEMA)


def downgrade() -> None:
    """Put one key back on the user row — the first by provider name.

    One column cannot hold two keys: a user with both keeps their Anthropic
    one ("claude" sorts first) and loses the other.
    """
    op.add_column(
        "users",
        sa.Column("api_key_encrypted", sa.String(500), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        "users",
        sa.Column("api_key_provider", sa.String(50), nullable=True),
        schema=_SCHEMA,
    )
    op.execute(
        f"""
        UPDATE {_SCHEMA}.users AS u
        SET api_key_encrypted = k.key_encrypted, api_key_provider = k.provider
        FROM (
            SELECT DISTINCT ON (user_id) user_id, provider, key_encrypted
            FROM {_SCHEMA}.user_api_keys
            ORDER BY user_id, provider
        ) AS k
        WHERE u.id = k.user_id
        """  # noqa: S608 — the schema name is a constant, not input
    )
    op.drop_table("user_api_keys", schema=_SCHEMA)
