"""Integration tests for mentoring repositories using in-memory SQLite."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.mentoring.infrastructure.orm import (
    Base,
    MeetingNoteModel,
    StudentModel,
)
from src.mentoring.infrastructure.repositories import (
    MeetingNoteRepository,
    StudentRepository,
)

_SQLITE_URL = "sqlite+aiosqlite:///:memory:"
_SCHEMA_TRANSLATE = {"schema_translate_map": {"mentoring": None}}

_NOW = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(_SQLITE_URL, execution_options=_SCHEMA_TRANSLATE)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


def _make_student(
    promotor_id: uuid.UUID | None = None,
    full_name: str = "Jan Kowalski",
    status: str = "active",
    created_at: datetime = _NOW,
) -> StudentModel:
    return StudentModel(
        id=uuid.uuid4(),
        promotor_id=promotor_id or uuid.uuid4(),
        full_name=full_name,
        field_of_study="Ekonomia",
        thesis_type="bachelor",
        status=status,
        created_at=created_at,
        updated_at=created_at,
    )


async def test_save_and_retrieve_student(session: AsyncSession) -> None:
    repo = StudentRepository(session)
    student = _make_student()
    await repo.save(student)

    found = await repo.find_by_id(student.id)
    assert found is not None
    assert found.full_name == "Jan Kowalski"
    assert found.current_topic is None


async def test_find_by_id_missing(session: AsyncSession) -> None:
    repo = StudentRepository(session)
    assert await repo.find_by_id(uuid.uuid4()) is None


async def test_find_all_filters_by_promotor(session: AsyncSession) -> None:
    repo = StudentRepository(session)
    mine = uuid.uuid4()
    await repo.save(_make_student(promotor_id=mine, full_name="Moja"))
    await repo.save(_make_student(full_name="Cudza"))

    assert [s.full_name for s in await repo.find_all(promotor_id=mine)] == ["Moja"]
    assert len(await repo.find_all()) == 2


async def test_find_all_filters_by_status(session: AsyncSession) -> None:
    repo = StudentRepository(session)
    await repo.save(_make_student(full_name="Aktywna", status="active"))
    await repo.save(_make_student(full_name="Zarchiwizowany", status="archived"))

    found = await repo.find_all(status="archived")
    assert [s.full_name for s in found] == ["Zarchiwizowany"]


async def test_find_all_returns_newest_first(session: AsyncSession) -> None:
    repo = StudentRepository(session)
    await repo.save(_make_student(full_name="Starszy", created_at=_NOW))
    await repo.save(
        _make_student(full_name="Nowszy", created_at=_NOW + timedelta(days=1))
    )

    assert [s.full_name for s in await repo.find_all()] == ["Nowszy", "Starszy"]


async def test_update_persists_topic(session: AsyncSession) -> None:
    repo = StudentRepository(session)
    student = _make_student()
    await repo.save(student)

    student.current_topic = "Instytucje a wzrost"
    student.current_topic_set_at = _NOW
    await repo.update(student)

    reloaded = await repo.find_by_id(student.id)
    assert reloaded is not None
    assert reloaded.current_topic == "Instytucje a wzrost"


async def test_delete_student(session: AsyncSession) -> None:
    repo = StudentRepository(session)
    student = _make_student()
    await repo.save(student)

    await repo.delete(student.id)
    assert await repo.find_by_id(student.id) is None


async def test_delete_missing_student_is_noop(session: AsyncSession) -> None:
    repo = StudentRepository(session)
    await repo.delete(uuid.uuid4())  # must not raise


# ---------- meeting notes ----------


def _make_note(
    student_id: uuid.UUID,
    content: str = "Notatka",
    occurred_at: datetime = _NOW,
) -> MeetingNoteModel:
    return MeetingNoteModel(
        id=uuid.uuid4(),
        student_id=student_id,
        promotor_id=uuid.uuid4(),
        occurred_at=occurred_at,
        content=content,
        created_at=_NOW,
    )


async def test_notes_are_scoped_to_one_student(session: AsyncSession) -> None:
    students = StudentRepository(session)
    notes = MeetingNoteRepository(session)
    mine = _make_student()
    other = _make_student()
    await students.save(mine)
    await students.save(other)

    await notes.save(_make_note(mine.id, content="Moja notatka"))
    await notes.save(_make_note(other.id, content="Cudza notatka"))

    found = await notes.find_by_student(mine.id)
    assert [n.content for n in found] == ["Moja notatka"]


async def test_notes_ordered_by_meeting_date_desc(session: AsyncSession) -> None:
    students = StudentRepository(session)
    notes = MeetingNoteRepository(session)
    student = _make_student()
    await students.save(student)

    await notes.save(_make_note(student.id, content="Pierwsze", occurred_at=_NOW))
    await notes.save(
        _make_note(student.id, content="Drugie", occurred_at=_NOW + timedelta(days=7))
    )

    assert [n.content for n in await notes.find_by_student(student.id)] == [
        "Drugie",
        "Pierwsze",
    ]
