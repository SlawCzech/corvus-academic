"""Deleting a student and deleting one action — nothing may be left behind.

The point of these tests is what remains afterwards: no file stranded in
`draft_files` (no cascade reaches it), no result kept in the agent, and — when
the agent cannot be told — nothing deleted at all rather than half of it.
"""

import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.mentoring.application.action_service import ActionService
from src.mentoring.application.draft_service import DraftService
from src.mentoring.application.exceptions import (
    ActionNotFoundError,
    AgentUnavailableError,
    StudentNotFoundError,
)
from src.mentoring.application.student_deletion import StudentDeletionService
from src.mentoring.application.student_service import Caller, StudentService
from src.mentoring.domain.action import ActionType
from src.mentoring.domain.student import Student, ThesisType
from src.mentoring.infrastructure.orm import (
    AgentActionModel,
    Base,
    DraftFileModel,
    MeetingNoteModel,
    StudentModel,
    ThesisDraftModel,
)
from src.mentoring.infrastructure.repositories import (
    AgentActionRepository,
    MeetingNoteRepository,
    StudentRepository,
    ThesisDraftRepository,
)
from src.shared.sql_file_store import SqlFileStore
from tests.test_mentoring.fakes import FakeAgentClient, docx_bytes, note_payload

_SQLITE_URL = "sqlite+aiosqlite:///:memory:"
_SCHEMA_TRANSLATE = {"schema_translate_map": {"mentoring": None}}

PROMOTOR = Caller(user_id=uuid.UUID("00000000-0000-0000-0000-0000000000a1"))
OTHER = Caller(user_id=uuid.UUID("00000000-0000-0000-0000-0000000000a2"))
TOKEN = "header.payload.signature"  # noqa: S105


class _Env:
    def __init__(self, session: AsyncSession, agent: FakeAgentClient) -> None:
        self.session = session
        self.agent = agent
        self.students = StudentService(
            StudentRepository(session), MeetingNoteRepository(session)
        )
        drafts = ThesisDraftRepository(session)
        files = SqlFileStore(session, DraftFileModel)
        self.drafts = DraftService(self.students, drafts, files)
        self.actions = ActionService(
            self.students, AgentActionRepository(session), drafts, agent
        )
        self.deletion = StudentDeletionService(
            self.students, StudentRepository(session), drafts, files, agent
        )

    async def count(self, model: Any, **where: object) -> int:  # noqa: ANN401
        stmt = select(func.count()).select_from(model)
        for column, value in where.items():
            stmt = stmt.where(getattr(model, column) == value)
        return int((await self.session.execute(stmt)).scalar_one())


@pytest.fixture
async def env() -> AsyncGenerator[_Env, None]:
    engine = create_async_engine(_SQLITE_URL, execution_options=_SCHEMA_TRANSLATE)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield _Env(session, FakeAgentClient())
    await engine.dispose()


async def _student_with_everything(env: _Env, caller: Caller = PROMOTOR) -> Student:
    """A student with two versions (files and all), a note and an action."""
    student = await env.students.create(
        caller,
        full_name="Jan Kowalski",
        field_of_study="Ekonomia",
        thesis_type=ThesisType.BACHELOR,
    )
    for _ in range(2):
        await env.drafts.upload(
            caller, student.id, filename="praca.docx", data=docx_bytes()
        )
    await env.students.add_meeting_note(caller, student.id, content="Spotkanie 1")
    await env.actions.trigger(
        caller, student.id, action_type=ActionType.PROPOSE_TOPIC, token=TOKEN
    )
    return student


# ---------- deleting a student ----------


async def test_deleting_a_student_leaves_nothing_behind(env: _Env) -> None:
    student = await _student_with_everything(env)
    assert await env.count(DraftFileModel) == 2

    await env.deletion.delete(PROMOTOR, student.id, TOKEN)

    assert await env.count(StudentModel, id=student.id) == 0
    assert await env.count(ThesisDraftModel, student_id=student.id) == 0
    assert await env.count(MeetingNoteModel, student_id=student.id) == 0
    assert await env.count(AgentActionModel, student_id=student.id) == 0
    # No cascade reaches the files — they have to be deleted on purpose.
    assert await env.count(DraftFileModel) == 0
    assert env.agent.deleted_students == [student.id]


async def test_deleting_one_student_leaves_the_others(env: _Env) -> None:
    doomed = await _student_with_everything(env)
    kept = await _student_with_everything(env)

    await env.deletion.delete(PROMOTOR, doomed.id, TOKEN)

    assert await env.count(ThesisDraftModel, student_id=kept.id) == 2
    assert await env.count(DraftFileModel) == 2
    assert await env.count(AgentActionModel, student_id=kept.id) == 1


async def test_nothing_is_deleted_when_the_agent_cannot_be_told(env: _Env) -> None:
    """The results live in the agent too; half a deletion is not one."""
    student = await _student_with_everything(env)
    env.agent.unavailable = True

    with pytest.raises(AgentUnavailableError):
        await env.deletion.delete(PROMOTOR, student.id, TOKEN)

    assert await env.count(StudentModel, id=student.id) == 1
    assert await env.count(DraftFileModel) == 2


async def test_another_promotors_student_cannot_be_deleted(env: _Env) -> None:
    student = await _student_with_everything(env, OTHER)

    with pytest.raises(StudentNotFoundError):
        await env.deletion.delete(PROMOTOR, student.id, TOKEN)

    assert await env.count(StudentModel, id=student.id) == 1
    assert env.agent.deleted_students == []


# ---------- deleting one action ----------


async def test_deleting_an_action_removes_it_here_and_in_the_agent(
    env: _Env,
) -> None:
    student = await _student_with_everything(env)
    [action] = await env.actions.list_actions(PROMOTOR, student.id, TOKEN)

    await env.actions.delete(PROMOTOR, student.id, action.id, TOKEN)

    assert await env.actions.list_actions(PROMOTOR, student.id, TOKEN) == []
    assert env.agent.deleted == ["task-1"]
    with pytest.raises(ActionNotFoundError):
        await env.actions.get_action(PROMOTOR, student.id, action.id, TOKEN)


async def test_a_note_keeps_its_text_when_its_action_is_deleted(env: _Env) -> None:
    student = await _student_with_everything(env)
    action = await env.actions.trigger(
        PROMOTOR,
        student.id,
        action_type=ActionType.DRAFT_MEETING_NOTE,
        token=TOKEN,
        detail="zakres rozdz. 2",
    )
    env.agent.completes_with(note_payload("Omówiliśmy zakres rozdziału 2."))
    await env.actions.get_action(PROMOTOR, student.id, action.id, TOKEN)
    await env.actions.accept(PROMOTOR, student.id, action.id)

    await env.actions.delete(PROMOTOR, student.id, action.id, TOKEN)

    notes = await env.students.list_meeting_notes(PROMOTOR, student.id)
    drafted = [n for n in notes if n.content == "Omówiliśmy zakres rozdziału 2."]
    assert len(drafted) == 1
    assert drafted[0].source_action_id is None


async def test_an_action_is_kept_when_the_agent_cannot_be_told(env: _Env) -> None:
    student = await _student_with_everything(env)
    [action] = await env.actions.list_actions(PROMOTOR, student.id, TOKEN)
    env.agent.unavailable = True

    with pytest.raises(AgentUnavailableError):
        await env.actions.delete(PROMOTOR, student.id, action.id, TOKEN)

    assert await env.count(AgentActionModel, id=action.id) == 1
