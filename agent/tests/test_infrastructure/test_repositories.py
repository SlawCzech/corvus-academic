"""Tests for AgentTaskRepository against in-memory SQLite."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.domain.action import ActionType, TaskStatus
from src.infrastructure.models import AgentTaskModel, Base, GuidelineChunkModel
from src.infrastructure.repositories import (
    AgentTaskRepository,
    GuidelineChunkRepository,
)

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


async def test_a_cancelled_task_stays_cancelled(repo: AgentTaskRepository) -> None:
    """A worker finishing after the revoke must not bring the task back."""
    await repo.save(_task("task-1", status=TaskStatus.RUNNING))
    await repo.update_status("task-1", TaskStatus.CANCELLED)

    await repo.update_status("task-1", TaskStatus.COMPLETED, result={"summary": "x"})

    found = await repo.find_by_task_id("task-1")
    assert found is not None
    assert found.status == TaskStatus.CANCELLED
    assert found.result is None


async def test_update_status_reports_missing_row(repo: AgentTaskRepository) -> None:
    assert await repo.update_status("ghost", TaskStatus.COMPLETED) is False


# ---------- guideline chunks ----------
#
# Storage and replacement are covered here; the similarity search itself is
# pgvector's `<=>` operator, which SQLite has no answer for, so it is verified
# against the real database in the phase's end-to-end run.


@pytest.fixture
async def guidelines() -> AsyncGenerator[GuidelineChunkRepository, None]:
    engine = create_async_engine(_SQLITE_URL, execution_options=_SCHEMA_TRANSLATE)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield GuidelineChunkRepository(session)
    await engine.dispose()


def _chunk(
    section: str,
    model: str = "nomic-embed-text",
    thesis_type: str = "bachelor",
    always: bool = False,
) -> GuidelineChunkModel:
    return GuidelineChunkModel(
        id=uuid.uuid4(),
        thesis_type=thesis_type,
        section=section,
        chunk_text=f"## {section}",
        embedding_model=model,
        dimensions=3,
        embedding=[0.1, 0.2, 0.3],
        always_include=always,
        created_at=_NOW,
    )


async def test_ingestion_stores_chunks(
    guidelines: GuidelineChunkRepository,
) -> None:
    stored = await guidelines.replace_for_type(
        "bachelor", "nomic-embed-text", [_chunk("1."), _chunk("2.")]
    )

    assert stored == 2
    assert await guidelines.count("bachelor", "nomic-embed-text") == 2


async def test_ingestion_is_idempotent(
    guidelines: GuidelineChunkRepository,
) -> None:
    """Running it twice leaves one copy, not two."""
    await guidelines.replace_for_type(
        "bachelor", "nomic-embed-text", [_chunk("1."), _chunk("2.")]
    )
    await guidelines.replace_for_type(
        "bachelor", "nomic-embed-text", [_chunk("1.")]
    )

    assert await guidelines.count("bachelor", "nomic-embed-text") == 1


async def test_reingestion_leaves_other_models_alone(
    guidelines: GuidelineChunkRepository,
) -> None:
    """Whoever still runs the other model still needs its vectors."""
    await guidelines.replace_for_type("bachelor", "other-model", [_chunk("1.")])

    await guidelines.replace_for_type(
        "bachelor", "nomic-embed-text", [_chunk("1."), _chunk("2.")]
    )

    assert await guidelines.count("bachelor", "other-model") == 1
    assert await guidelines.count("bachelor", "nomic-embed-text") == 2


async def test_thesis_types_are_ingested_independently(
    guidelines: GuidelineChunkRepository,
) -> None:
    await guidelines.replace_for_type(
        "master_article",
        "nomic-embed-text",
        [_chunk("1.", thesis_type="master_article")],
    )

    await guidelines.replace_for_type(
        "bachelor", "nomic-embed-text", [_chunk("1.")]
    )

    assert await guidelines.count("master_article", "nomic-embed-text") == 1
