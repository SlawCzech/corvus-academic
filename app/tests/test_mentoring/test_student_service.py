"""Unit tests for StudentService against in-memory SQLite.

Ownership is the rule worth testing without HTTP in the way: the service —
not the router — decides what a caller may see, and returns the same
"not found" for a student that does not exist and one belonging to someone
else. (The router tests cover the same rule end-to-end; these cover it
directly, which is also how identity's application layer is tested.)
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.mentoring.application.exceptions import StudentNotFoundError
from src.mentoring.application.student_service import Caller, StudentService
from src.mentoring.domain.student import Student, StudentStatus, ThesisType
from src.mentoring.infrastructure.orm import Base
from src.mentoring.infrastructure.repositories import (
    MeetingNoteRepository,
    StudentRepository,
)

_SQLITE_URL = "sqlite+aiosqlite:///:memory:"
_SCHEMA_TRANSLATE = {"schema_translate_map": {"mentoring": None}}

PROMOTOR = Caller(user_id=uuid.UUID("00000000-0000-0000-0000-0000000000a1"))
OTHER = Caller(user_id=uuid.UUID("00000000-0000-0000-0000-0000000000a2"))
ADMIN = Caller(
    user_id=uuid.UUID("00000000-0000-0000-0000-0000000000a3"), can_view_all=True
)


@pytest.fixture
async def service() -> AsyncGenerator[StudentService, None]:
    engine = create_async_engine(_SQLITE_URL, execution_options=_SCHEMA_TRANSLATE)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield StudentService(StudentRepository(session), MeetingNoteRepository(session))
    await engine.dispose()


async def _add(
    service: StudentService,
    caller: Caller = PROMOTOR,
    full_name: str = "Jan Kowalski",
) -> Student:
    return await service.create(
        caller,
        full_name=full_name,
        field_of_study="Ekonomia",
        thesis_type=ThesisType.BACHELOR,
    )


# ---------- create ----------


async def test_create_assigns_caller_as_promotor(service: StudentService) -> None:
    student = await _add(service)
    assert student.promotor_id == PROMOTOR.user_id
    assert student.status is StudentStatus.ACTIVE


async def test_create_validates_before_touching_the_database(
    service: StudentService,
) -> None:
    with pytest.raises(ValueError, match="full_name"):
        await _add(service, full_name="   ")
    assert await service.list_students(ADMIN) == []


# ---------- visibility ----------


async def test_list_returns_only_the_callers_students(
    service: StudentService,
) -> None:
    await _add(service, PROMOTOR, "Moja Studentka")
    await _add(service, OTHER, "Cudzy Student")

    assert [s.full_name for s in await service.list_students(PROMOTOR)] == [
        "Moja Studentka"
    ]


async def test_admin_lists_every_roster(service: StudentService) -> None:
    await _add(service, PROMOTOR, "Moja Studentka")
    await _add(service, OTHER, "Cudzy Student")

    assert len(await service.list_students(ADMIN)) == 2


async def test_list_filters_by_status(service: StudentService) -> None:
    active = await _add(service, PROMOTOR, "Aktywna")
    archived = await _add(service, PROMOTOR, "Zarchiwizowany")
    await service.update(PROMOTOR, archived.id, status=StudentStatus.ARCHIVED)

    found = await service.list_students(PROMOTOR, status=StudentStatus.ACTIVE)
    assert [s.id for s in found] == [active.id]


async def test_get_other_promotors_student_raises_not_found(
    service: StudentService,
) -> None:
    student = await _add(service, OTHER)
    with pytest.raises(StudentNotFoundError):
        await service.get(PROMOTOR, student.id)


async def test_get_unknown_student_raises_not_found(service: StudentService) -> None:
    with pytest.raises(StudentNotFoundError):
        await service.get(PROMOTOR, uuid.uuid4())


async def test_admin_gets_any_student(service: StudentService) -> None:
    student = await _add(service, OTHER)
    assert (await service.get(ADMIN, student.id)).id == student.id


# ---------- update ----------


async def test_update_sets_topic_and_stamps_time(service: StudentService) -> None:
    student = await _add(service)
    updated = await service.update(
        PROMOTOR, student.id, current_topic="Instytucje a wzrost"
    )
    assert updated.current_topic == "Instytucje a wzrost"
    assert updated.current_topic_set_at is not None


async def test_update_without_fields_changes_nothing(
    service: StudentService,
) -> None:
    student = await _add(service)
    await service.update(PROMOTOR, student.id, current_topic="Temat")

    unchanged = await service.update(PROMOTOR, student.id)
    assert unchanged.current_topic == "Temat"
    assert unchanged.status is StudentStatus.ACTIVE


async def test_update_rejects_blank_topic(service: StudentService) -> None:
    student = await _add(service)
    with pytest.raises(ValueError, match="topic"):
        await service.update(PROMOTOR, student.id, current_topic="  ")


async def test_update_edits_the_students_details(service: StudentService) -> None:
    student = await _add(service)
    updated = await service.update(
        PROMOTOR,
        student.id,
        full_name="Anna Nowak",
        field_of_study="Finanse",
        thesis_type=ThesisType.MASTER_ARTICLE,
        index_number="12345",
        set_index_number=True,
    )

    stored = await service.get(PROMOTOR, student.id)
    assert stored == updated
    assert stored.full_name == "Anna Nowak"
    assert stored.field_of_study == "Finanse"
    assert stored.thesis_type is ThesisType.MASTER_ARTICLE
    assert stored.index_number == "12345"


async def test_update_clears_index_number_only_when_asked(
    service: StudentService,
) -> None:
    student = await _add(service)
    await service.update(
        PROMOTOR, student.id, index_number="12345", set_index_number=True
    )

    kept = await service.update(PROMOTOR, student.id, full_name="Anna Nowak")
    cleared = await service.update(
        PROMOTOR, student.id, index_number=None, set_index_number=True
    )

    assert kept.index_number == "12345"
    assert cleared.index_number is None


async def test_update_clears_the_topic(service: StudentService) -> None:
    student = await _add(service)
    await service.update(PROMOTOR, student.id, current_topic="Temat")

    cleared = await service.update(PROMOTOR, student.id, clear_topic=True)

    assert cleared.current_topic is None
    assert cleared.current_topic_set_at is None


async def test_update_rejects_blank_name(service: StudentService) -> None:
    student = await _add(service)
    with pytest.raises(ValueError, match="full_name"):
        await service.update(PROMOTOR, student.id, full_name="  ")
    assert (await service.get(PROMOTOR, student.id)).full_name == "Jan Kowalski"


async def test_update_other_promotors_student_raises_not_found(
    service: StudentService,
) -> None:
    student = await _add(service, OTHER)
    with pytest.raises(StudentNotFoundError):
        await service.update(PROMOTOR, student.id, status=StudentStatus.ARCHIVED)


# ---------- meeting notes ----------


async def test_add_note_records_the_caller_as_author(
    service: StudentService,
) -> None:
    student = await _add(service, OTHER)
    note = await service.add_meeting_note(ADMIN, student.id, content="Wpis admina")

    assert note.promotor_id == ADMIN.user_id
    assert note.student_id == student.id
    assert note.is_ai_drafted is False


async def test_add_note_defaults_occurred_at_to_now(
    service: StudentService,
) -> None:
    student = await _add(service)
    before = datetime.now(UTC) - timedelta(seconds=1)
    note = await service.add_meeting_note(PROMOTOR, student.id, content="Ad hoc")
    # SQLite has no timestamptz: the value refreshed from it comes back naive
    # (it is UTC), while Postgres keeps it aware. Compare on the same footing.
    assert note.occurred_at.replace(tzinfo=UTC) >= before


async def test_add_note_keeps_action_provenance(service: StudentService) -> None:
    """Phase 2 accepts an AI draft into a note — the link is carried here."""
    student = await _add(service)
    action_id = uuid.uuid4()
    note = await service.add_meeting_note(
        PROMOTOR, student.id, content="Z draftu", source_action_id=action_id
    )
    assert note.source_action_id == action_id
    assert note.is_ai_drafted is True


async def test_add_note_rejects_blank_content(service: StudentService) -> None:
    student = await _add(service)
    with pytest.raises(ValueError, match="content"):
        await service.add_meeting_note(PROMOTOR, student.id, content="\t")


async def test_add_note_to_invisible_student_raises_not_found(
    service: StudentService,
) -> None:
    student = await _add(service, OTHER)
    with pytest.raises(StudentNotFoundError):
        await service.add_meeting_note(PROMOTOR, student.id, content="Nie moja")


async def test_notes_are_listed_newest_meeting_first(
    service: StudentService,
) -> None:
    student = await _add(service)
    older = datetime(2026, 3, 1, 10, 0, tzinfo=UTC)
    await service.add_meeting_note(
        PROMOTOR, student.id, content="Pierwsze", occurred_at=older
    )
    await service.add_meeting_note(
        PROMOTOR,
        student.id,
        content="Drugie",
        occurred_at=older + timedelta(days=7),
    )

    notes = await service.list_meeting_notes(PROMOTOR, student.id)
    assert [n.content for n in notes] == ["Drugie", "Pierwsze"]


async def test_listing_notes_of_invisible_student_raises_not_found(
    service: StudentService,
) -> None:
    student = await _add(service, OTHER)
    with pytest.raises(StudentNotFoundError):
        await service.list_meeting_notes(PROMOTOR, student.id)
