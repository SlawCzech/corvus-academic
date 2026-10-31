"""Retention and hard delete reach fragments too."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.mentoring.application.draft_service import DraftService
from src.mentoring.application.fragment_service import (
    FragmentService,
    FragmentUpload,
)
from src.mentoring.application.retention_service import RetentionService
from src.mentoring.application.student_deletion import StudentDeletionService
from src.mentoring.application.student_service import Caller, StudentService
from src.mentoring.domain.fragment import FragmentVerdict, ThesisFragment
from src.mentoring.domain.retention import RetentionPolicy
from src.mentoring.domain.student import Student, StudentStatus, ThesisType
from src.mentoring.infrastructure.orm import (
    Base,
    DraftFileModel,
    ThesisFragmentModel,
    ThesisPartModel,
)
from src.mentoring.infrastructure.repositories import (
    MeetingNoteRepository,
    StudentRepository,
    ThesisDraftRepository,
    ThesisFragmentRepository,
    ThesisPartRepository,
)
from src.shared.sql_file_store import SqlFileStore
from tests.test_mentoring.fakes import FakeAgentClient, docx_bytes

_SQLITE_URL = "sqlite+aiosqlite:///:memory:"
_SCHEMA_TRANSLATE = {"schema_translate_map": {"mentoring": None}}
_T0 = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
_POLICY = RetentionPolicy()

PROMOTOR = Caller(user_id=uuid.UUID("00000000-0000-0000-0000-0000000000a1"))
TOKEN = "header.payload.signature"  # noqa: S105


class _Env:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.agent = FakeAgentClient()
        self.students = StudentService(
            StudentRepository(session), MeetingNoteRepository(session)
        )
        drafts = ThesisDraftRepository(session)
        fragments = ThesisFragmentRepository(session)
        files = SqlFileStore(session, DraftFileModel)
        self.drafts = DraftService(self.students, drafts, files)
        self.fragments = FragmentService(
            self.students, ThesisPartRepository(session), fragments, files
        )
        self.fragment_rows = fragments
        self.retention = RetentionService(
            StudentRepository(session), drafts, fragments, files
        )
        self.deletion = StudentDeletionService(
            self.students,
            StudentRepository(session),
            drafts,
            files,
            self.agent,
            fragments,
        )

    async def student(self) -> Student:
        return await self.students.create(
            PROMOTOR,
            full_name="Jan Kowalski",
            field_of_study="Ekonomia",
            thesis_type=ThesisType.BACHELOR,
        )

    async def fragment(self, student: Student) -> ThesisFragment:
        return await self.fragments.upload(
            PROMOTOR,
            student.id,
            "Rozdział 1",
            FragmentUpload(filename="r1.docx", data=docx_bytes("Rozdział pierwszy.")),
            received_on=date(2026, 5, 1),
        )

    async def count(self, model: Any) -> int:  # noqa: ANN401
        stmt = select(func.count()).select_from(model)
        return int((await self.session.execute(stmt)).scalar_one())


@pytest.fixture
async def env() -> AsyncGenerator[_Env, None]:
    engine = create_async_engine(_SQLITE_URL, execution_options=_SCHEMA_TRANSLATE)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield _Env(session)
    await engine.dispose()


def _student(**fields: Any) -> Student:  # noqa: ANN401
    return Student(
        id=uuid.uuid4(),
        promotor_id=uuid.uuid4(),
        full_name="Jan Kowalski",
        field_of_study="Ekonomia",
        thesis_type=ThesisType.BACHELOR,
        **fields,
    )


def _fragment(student: Student, **fields: Any) -> ThesisFragment:  # noqa: ANN401
    return ThesisFragment(
        id=uuid.uuid4(),
        student_id=student.id,
        part_id=uuid.uuid4(),
        round_number=1,
        received_on=date(2026, 5, 1),
        text="Rozdział.",
        format="text",
        uploaded_by=uuid.uuid4(),
        **fields,
    )


def test_nothing_is_due_while_the_student_is_active() -> None:
    student = _student()

    assert _POLICY.fragment_purge_due_at(student, _fragment(student)) is None


def test_accepting_a_version_starts_the_fragments_clock() -> None:
    student = _student()
    student.accept_draft(uuid.uuid4(), at=_T0)

    due = _POLICY.fragment_purge_due_at(student, _fragment(student))

    assert due == _T0 + timedelta(days=30)


def test_closing_a_student_starts_it_too() -> None:
    student = _student()
    student.change_status(StudentStatus.GRADUATED, at=_T0)

    due = _POLICY.fragment_purge_due_at(student, _fragment(student))

    assert due == _T0 + timedelta(days=150)


def test_a_purged_fragment_is_never_due_again() -> None:
    student = _student()
    student.accept_draft(uuid.uuid4(), at=_T0)
    fragment = _fragment(student)
    fragment.purge(_T0)

    assert _POLICY.fragment_purge_due_at(student, fragment) is None


async def test_sweep_purges_the_text_and_file_and_keeps_the_feedback(
    env: _Env,
) -> None:
    student = await env.student()
    fragment = await env.fragment(student)
    model = await env.fragment_rows.find_by_id(fragment.id)
    assert model is not None
    model.verdict = str(FragmentVerdict.NEEDS_CHANGES)
    model.feedback = "Dodaj próbę."
    await env.fragment_rows.update(model)
    await env.students.update(PROMOTOR, student.id, status=StudentStatus.GRADUATED)

    now = datetime.now(UTC) + timedelta(days=151)
    purged = await env.retention.sweep(now)

    assert purged == 1
    await env.session.refresh(model)
    assert model.text is None
    assert model.file_id is None
    assert model.purged_at is not None
    assert model.feedback == "Dodaj próbę."
    assert model.char_count > 0
    assert await env.count(DraftFileModel) == 0
    assert await env.retention.sweep(now) == 0


async def test_a_fragment_keeps_an_accepted_version_accepted(env: _Env) -> None:
    student = await env.student()
    draft = await env.drafts.upload(
        PROMOTOR, student.id, filename="praca.docx", data=docx_bytes()
    )
    await env.drafts.accept(PROMOTOR, student.id, draft.draft.id)

    await env.fragment(student)

    current = await env.students.get(PROMOTOR, student.id)
    assert current.accepted_draft_id == draft.draft.id


async def test_deleting_a_student_takes_the_fragments_and_their_files(
    env: _Env,
) -> None:
    student = await env.student()
    await env.fragment(student)
    await env.fragments.add_part(PROMOTOR, student.id, "Rozdział 2")
    assert await env.count(DraftFileModel) == 1

    await env.deletion.delete(PROMOTOR, student.id, TOKEN)

    assert await env.count(ThesisFragmentModel) == 0
    assert await env.count(ThesisPartModel) == 0
    # No cascade reaches the files — they have to be deleted on purpose.
    assert await env.count(DraftFileModel) == 0
