"""Tests for AgentTaskRepository against in-memory SQLite."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.domain.action import ActionType, TaskStatus
from src.infrastructure.models import AgentTaskModel, Base
from src.infrastructure.repositories import AgentTaskRepository

_SQLITE_URL = "sqlite+aiosqlite:///:memory:"
_SCHEMA_TRANSLATE = {"schema_translate_map": {"analysis": None}}

USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
_NOW = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
async def repo() -> AsyncGenerator[AgentTaskRepository, None]:
    engine = create_async_engine(_SQLITE_URL, execution_options=_SCHEMA_TRANSLATE)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield AgentTaskRepository(session)
    await engine.dispose()


def _task(
    task_id: str,
    user_id: uuid.UUID = USER_ID,
    status: TaskStatus = TaskStatus.PENDING,
    created_at: datetime = _NOW,
) -> AgentTaskModel:
    return AgentTaskModel(
        id=uuid.uuid4(),
        task_id=task_id,
        user_id=user_id,
        action_type=ActionType.GENERATE_REVIEW,
        status=status,
        created_at=created_at,
        updated_at=created_at,
    )


async def test_save_and_find_by_task_id(repo: AgentTaskRepository) -> None:
    await repo.save(_task("task-1"))
    found = await repo.find_by_task_id("task-1")
    assert found is not None
    assert found.status == TaskStatus.PENDING


async def test_find_by_task_id_missing(repo: AgentTaskRepository) -> None:
    assert await repo.find_by_task_id("nope") is None


async def test_find_by_user_and_task_id_scopes_by_owner(
    repo: AgentTaskRepository,
) -> None:
    await repo.save(_task("task-1"))
    other = uuid.UUID("00000000-0000-0000-0000-0000000000ff")
    assert await repo.find_by_user_and_task_id(other, "task-1") is None
    assert await repo.find_by_user_and_task_id(USER_ID, "task-1") is not None


async def test_update_status_writes_result(repo: AgentTaskRepository) -> None:
    await repo.save(_task("task-1"))
    payload: dict[str, Any] = {"summary": "gotowe"}

    assert await repo.update_status("task-1", TaskStatus.COMPLETED, result=payload)

    found = await repo.find_by_task_id("task-1")
    assert found is not None
    assert found.status == TaskStatus.COMPLETED
    assert found.result == payload


async def test_update_status_keeps_earlier_result(repo: AgentTaskRepository) -> None:
    """A status-only update must not wipe an outcome already recorded."""
    await repo.save(_task("task-1"))
    await repo.update_status("task-1", TaskStatus.COMPLETED, result={"summary": "x"})

    await repo.update_status("task-1", TaskStatus.RUNNING)

    found = await repo.find_by_task_id("task-1")
    assert found is not None
    assert found.result == {"summary": "x"}


async def test_update_status_records_error(repo: AgentTaskRepository) -> None:
    await repo.save(_task("task-1"))
    await repo.update_status("task-1", TaskStatus.FAILED, error="Ollama unreachable")

    found = await repo.find_by_task_id("task-1")
    assert found is not None
    assert found.error == "Ollama unreachable"


async def test_update_status_reports_missing_row(repo: AgentTaskRepository) -> None:
    assert await repo.update_status("ghost", TaskStatus.COMPLETED) is False
