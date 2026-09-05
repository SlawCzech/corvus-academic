"""Alembic migration environment — async engine, identity schema only."""

import asyncio
from logging.config import fileConfig
from typing import Any

import sqlalchemy as sa
from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from src.identity.infrastructure.models import Base
from src.shared.settings import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

config.set_main_option("sqlalchemy.url", settings.database_url)

_IDENTITY_SCHEMA = "identity"


def include_object(
    obj: Any,  # noqa: ANN401
    name: str,
    type_: str,
    reflected: bool,
    compare_to: Any,  # noqa: ANN401
) -> bool:
    """Only manage objects that belong to the identity schema."""
    if type_ == "table":
        schema = getattr(obj, "schema", None)
        return schema == _IDENTITY_SCHEMA
    return True


def run_migrations_offline() -> None:
    """Run migrations without a live database connection (offline mode)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_object=include_object,
        version_table="alembic_version",
        version_table_schema=_IDENTITY_SCHEMA,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Execute migrations on a synchronous connection (called via run_sync).

    Schema creation is done BEFORE this call, in its own committed transaction,
    to avoid asyncpg's DDL-inside-savepoint catalog cache bug.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        include_object=include_object,
        version_table="alembic_version",
        version_table_schema=_IDENTITY_SCHEMA,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and delegate migration execution."""
    section: dict[str, Any] = config.get_section(config.config_ini_section) or {}
    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    # Step 1: ensure the schema exists in its own committed transaction.
    # This must happen BEFORE Alembic opens its transaction, because asyncpg
    # cannot reliably use DDL (CREATE TABLE) inside a SAVEPOINT — the catalog
    # cache gets stale and subsequent prepared statements fail.
    async with connectable.connect() as conn:
        await conn.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {_IDENTITY_SCHEMA}"))
        await conn.commit()

    # Step 2: run migrations in a fresh connection.
    async with connectable.connect() as conn:
        await conn.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online (connected) migration mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
