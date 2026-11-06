"""Durable task-status writes from the Celery worker.

The worker is synchronous while the rest of the service speaks async
SQLAlchemy, so each write opens its own short-lived engine under
``asyncio.run``. That is cheap next to an LLM call measured in minutes, and
it avoids sharing an engine across event loops that the worker creates and
destroys per task.

Failures here are logged, never raised: losing a status write must not fail
(and then retry) an analysis that actually succeeded. A status that carries an
outcome is written again a few times when the database is briefly away (a
restart, a dropped connection), so a run that finished does not lose its
result to a blink. An outage longer than that still leaves a stale row — see
docs/technical-debt.md.
"""

import asyncio
import time
from typing import Any

import structlog
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.domain.action import TaskStatus
from src.infrastructure.repositories import AgentTaskRepository
from src.infrastructure.settings import settings
from src.infrastructure.usage import Usage

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Seconds to wait before each further attempt at a status that carries an
# outcome: about a minute in all, enough for Postgres to restart. `running`
# gets one attempt — losing it costs nothing, the outcome overwrites it.
_STATUS_WRITE_RETRY_DELAYS = (2.0, 5.0, 15.0, 30.0)


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
            return await AgentTaskRepository(session).update_progress(task_id, progress)
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


async def _read_status(task_id: str) -> str | None:
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            model = await AgentTaskRepository(session).find_by_task_id(task_id)
            return model.status if model is not None else None
    finally:
        await engine.dispose()


def read_task_status(task_id: str | None) -> str | None:
    """The task's status as its row has it; None when unknown.

    A failed read is unknown too: the caller goes ahead as if the row said
    nothing, rather than drop a task because the database blinked.
    """
    if not task_id:
        return None
    try:
        return asyncio.run(_read_status(task_id))
    except Exception as exc:
        logger.warning("task_status_read_failed", task_id=task_id, error=str(exc))
        return None


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
    """Persist a task's status to Postgres, swallowing any failure.

    An outcome (anything but ``running``) is tried again after a pause when
    the database could not be reached; any other error is not worth waiting
    on. Once the attempts run out it is logged as ``task_status_write_failed``,
    which the server's watch alerts on.
    """
    if not task_id:
        logger.warning("task_status_skipped_no_task_id", status=status)
        return
    delays = () if status == TaskStatus.RUNNING else _STATUS_WRITE_RETRY_DELAYS
    attempt = 0
    while True:
        try:
            found = asyncio.run(_write(task_id, status, result, error, error_code))
            break
        except Exception as exc:
            if attempt < len(delays) and _is_transient(exc):
                logger.warning(
                    "task_status_write_retrying",
                    task_id=task_id,
                    status=status,
                    attempt=attempt + 1,
                    error=str(exc),
                )
            else:
                logger.error(
                    "task_status_write_failed",
                    task_id=task_id,
                    status=status,
                    attempts=attempt + 1,
                    error=str(exc),
                )
                return
        # Outside the `try`: a time limit that lands while waiting is the
        # task's to handle, not a failed write.
        time.sleep(delays[attempt])
        attempt += 1
    if not found:
        logger.warning("task_status_row_missing", task_id=task_id, status=status)


def _is_transient(exc: Exception) -> bool:
    """Whether the database was unreachable, rather than the write wrong."""
    if isinstance(exc, OperationalError | InterfaceError | OSError | TimeoutError):
        return True
    return isinstance(exc, DBAPIError) and exc.connection_invalidated
