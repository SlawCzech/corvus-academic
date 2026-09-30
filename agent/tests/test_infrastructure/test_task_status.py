"""Tests for the worker's durable status writer.

The writer is deliberately forgiving: an analysis that took minutes of LLM
time must not be retried just because the status write failed.
"""

import asyncio
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from src.domain.action import ActionType, TaskStatus
from src.infrastructure.models import AgentTaskModel, Base
from src.infrastructure.repositories import AgentTaskRepository
from src.infrastructure.task_status import record_task_progress, record_task_status

_SCHEMA_TRANSLATE = {"schema_translate_map": {"analysis": None}}


def test_writes_through_to_the_repository() -> None:
    with patch("src.infrastructure.task_status._write", return_value=True) as write:
        record_task_status("task-1", TaskStatus.COMPLETED, result={"summary": "x"})

    assert write.call_args.args[0] == "task-1"
    assert write.call_args.args[1] == TaskStatus.COMPLETED
    assert write.call_args.args[2] == {"summary": "x"}


def test_database_failure_does_not_propagate() -> None:
    with patch(
        "src.infrastructure.task_status._write", side_effect=OSError("db down")
    ):
        record_task_status("task-1", TaskStatus.COMPLETED)  # must not raise


def test_missing_row_does_not_propagate() -> None:
    with patch("src.infrastructure.task_status._write", return_value=False):
        record_task_status("task-1", TaskStatus.RUNNING)  # must not raise


def test_without_task_id_nothing_is_written() -> None:
    with patch("src.infrastructure.task_status._write") as write:
        record_task_status(None, TaskStatus.RUNNING)

    write.assert_not_called()


def test_progress_writes_through_and_swallows_failures() -> None:
    progress = {"steps": ["a"], "done": ["a"]}
    with patch(
        "src.infrastructure.task_status._write_progress", return_value=True
    ) as write:
        record_task_progress("task-1", progress)
    assert write.call_args.args == ("task-1", progress)

    with patch(
        "src.infrastructure.task_status._write_progress",
        side_effect=OSError("db down"),
    ):
        record_task_progress("task-1", progress)  # must not raise

    with patch("src.infrastructure.task_status._write_progress") as write:
        record_task_progress(None, progress)
    write.assert_not_called()


# ---------- the write itself ----------


def test_write_reaches_the_database(tmp_path: Path) -> None:
    """End-to-end through the writer's own engine, on a file-backed SQLite.

    Covers what the mocked tests above cannot: that the worker's synchronous
    call really opens a session, finds the row by task_id and commits.
    """
    url = f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}"

    def _engine(*_args: object, **_kwargs: object) -> Any:  # noqa: ANN401
        return create_async_engine(url, execution_options=_SCHEMA_TRANSLATE)

    task_id = str(uuid.uuid4())

    async def _seed() -> None:
        engine = _engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            now = datetime.now(UTC)
            await AgentTaskRepository(session).save(
                AgentTaskModel(
                    id=uuid.uuid4(),
                    task_id=task_id,
                    user_id=uuid.uuid4(),
                    action_type=ActionType.PROPOSE_TOPIC,
                    status=TaskStatus.PENDING,
                    created_at=now,
                    updated_at=now,
                )
            )
        await engine.dispose()

    async def _read() -> AgentTaskModel | None:
        engine = _engine()
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            found = await AgentTaskRepository(session).find_by_task_id(task_id)
        await engine.dispose()
        return found

    asyncio.run(_seed())

    with patch("src.infrastructure.task_status.create_async_engine", _engine):
        record_task_status(task_id, TaskStatus.COMPLETED, result={"summary": "ok"})

    stored = asyncio.run(_read())
    assert stored is not None
    assert stored.status == TaskStatus.COMPLETED
    assert stored.result == {"summary": "ok"}
