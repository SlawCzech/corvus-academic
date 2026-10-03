"""Durable task-status writes from the Celery worker.

The worker is synchronous while the rest of the service speaks async
SQLAlchemy, so each write opens its own short-lived engine under
``asyncio.run``. That is cheap next to an LLM call measured in minutes, and
it avoids sharing an engine across event loops that the worker creates and
destroys per task.

Failures here are logged, never raised: losing a status write must not fail
(and then retry) an analysis that actually succeeded. The consequence is that
a database outage leaves a stale row — see docs/technical-debt.md.
"""

import asyncio
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.infrastructure.repositories import AgentTaskRepository
from src.infrastructure.settings import settings
from src.infrastructure.usage import Usage

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _write(
    task_id: str,
    status: str,
    result: dict[str, Any] | None,
    error: str | None,
    error_code: str | None = None,
) -> bool:
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            repo = AgentTaskRepository(session)
            return await repo.update_status(
                task_id, status, result=result, error=error, error_code=error_code
            )
    finally:
        await engine.dispose()


async def _write_progress(task_id: str, progress: dict[str, Any]) -> bool:
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            return await AgentTaskRepository(session).update_progress(
                task_id, progress
            )
    finally:
        await engine.dispose()


async def _write_usage(task_id: str, usage: Usage) -> bool:
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            return await AgentTaskRepository(session).add_usage(task_id, usage)
    finally:
        await engine.dispose()


def record_task_usage(task_id: str | None, usage: Usage | None) -> None:
    """Add the tokens one run spent to its task, swallowing any failure.

    A lost write undercounts what an action cost; it must never fail an
    action that has its result.
    """
    if not task_id or usage is None:
        return
    try:
        asyncio.run(_write_usage(task_id, usage))
    except Exception as exc:
        logger.warning("task_usage_write_failed", task_id=task_id, error=str(exc))


def record_task_progress(task_id: str | None, progress: dict[str, Any]) -> None:
    """Persist which nodes a running task has finished, swallowing any failure.

    Progress is a courtesy to whoever is watching; a write that fails costs
    them a checkmark, never the task.
    """
    if not task_id:
        return
    try:
        asyncio.run(_write_progress(task_id, progress))
    except Exception as exc:
        logger.warning("task_progress_write_failed", task_id=task_id, error=str(exc))


def record_task_status(
    task_id: str | None,
    status: str,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    error_code: str | None = None,
) -> None:
    """Persist a task's status to Postgres, swallowing any failure."""
    if not task_id:
        logger.warning("task_status_skipped_no_task_id", status=status)
        return
    try:
        found = asyncio.run(_write(task_id, status, result, error, error_code))
    except Exception as exc:
        logger.error(
            "task_status_write_failed",
            task_id=task_id,
            status=status,
            error=str(exc),
        )
        return
    if not found:
        logger.warning("task_status_row_missing", task_id=task_id, status=status)
