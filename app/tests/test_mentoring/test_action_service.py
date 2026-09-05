"""Unit tests for ActionService — the AI action lifecycle inside `app`.

The agent is faked: what matters here is that the attempt is recorded before
dispatch, that a promoter only ever sees their own students' actions, and
that accepting a proposal is what changes the student.
"""

import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.mentoring.application.action_service import (
    ActionNotFoundError,
    ActionService,
    UnsupportedActionError,
)
from src.mentoring.application.agent_client import AgentUnavailableError
from src.mentoring.application.student_service import (
    Caller,
    StudentNotFoundError,
    StudentService,
)
from src.mentoring.domain.action import ActionStatus, ActionType
from src.mentoring.domain.student import Student, ThesisType
from src.mentoring.infrastructure.models import Base
from src.mentoring.infrastructure.repositories import (
    AgentActionRepository,
    MeetingNoteRepository,
    StudentRepository,
)
from tests.test_mentoring.fakes import FakeAgentClient, topic_payload

_SQLITE_URL = "sqlite+aiosqlite:///:memory:"
_SCHEMA_TRANSLATE = {"schema_translate_map": {"mentoring": None}}

PROMOTOR = Caller(user_id=uuid.UUID("00000000-0000-0000-0000-0000000000a1"))
OTHER = Caller(user_id=uuid.UUID("00000000-0000-0000-0000-0000000000a2"))
TOKEN = "header.payload.signature"  # noqa: S105


class _Fixture:
    """The three collaborators a test needs, wired to one SQLite session."""

    def __init__(
        self, students: StudentService, actions: ActionService, agent: FakeAgentClient
    ) -> None:
        self.students = students
        self.actions = actions
        self.agent = agent


@pytest.fixture
async def env() -> AsyncGenerator[_Fixture, None]:
    engine = create_async_engine(_SQLITE_URL, execution_options=_SCHEMA_TRANSLATE)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        students = StudentService(
            StudentRepository(session), MeetingNoteRepository(session)
        )
        agent = FakeAgentClient()
        yield _Fixture(
            students,
            ActionService(students, AgentActionRepository(session), agent),
            agent,
        )
    await engine.dispose()


async def _student(env: _Fixture, caller: Caller = PROMOTOR) -> Student:
    return await env.students.create(
        caller,
        full_name="Jan Kowalski",
        field_of_study="Ekonomia",
        thesis_type=ThesisType.BACHELOR,
    )


# ---------- trigger ----------


async def test_trigger_records_the_attempt_and_dispatches(env: _Fixture) -> None:
    student = await _student(env)

    action = await env.actions.trigger(
        PROMOTOR,
        student.id,
        action_type=ActionType.PROPOSE_TOPIC,
        token=TOKEN,
        detail="coś ilościowego",
    )

    assert action.status is ActionStatus.PENDING
    assert action.task_id == env.agent.task_id
    assert action.detail == "coś ilościowego"
    assert env.agent.submitted[0]["action_id"] == action.id
    assert env.agent.submitted[0]["token"] == TOKEN


async def test_trigger_sends_the_assembled_context(env: _Fixture) -> None:
    """The agent is told about the student — it never reads the database."""
    student = await _student(env)
    await env.students.add_meeting_note(
        PROMOTOR, student.id, content="Student chce pracować na danych GUS"
    )

    await env.actions.trigger(
        PROMOTOR,
        student.id,
        action_type=ActionType.PROPOSE_TOPIC,
        token=TOKEN,
        detail="temat z komponentem ilościowym",
    )

    context = env.agent.submitted[0]["context"]
    assert context["field_of_study"] == "Ekonomia"
    assert context["thesis_type"] == "bachelor"
    assert context["detail"] == "temat z komponentem ilościowym"
    assert context["recent_notes"] == ["Student chce pracować na danych GUS"]


async def test_trigger_on_another_promotors_student_is_not_found(
    env: _Fixture,
) -> None:
    student = await _student(env, OTHER)

    with pytest.raises(StudentNotFoundError):
        await env.actions.trigger(
            PROMOTOR, student.id, action_type=ActionType.PROPOSE_TOPIC, token=TOKEN
        )
    assert env.agent.submitted == []


async def test_action_without_context_assembly_is_rejected(env: _Fixture) -> None:
    """Phase 3 action types must not reach the agent as unqueueable work."""
    student = await _student(env)

    with pytest.raises(UnsupportedActionError):
        await env.actions.trigger(
            PROMOTOR, student.id, action_type=ActionType.CHECK_PROGRESS, token=TOKEN
        )
    assert await env.actions.list_actions(PROMOTOR, student.id) == []


async def test_failed_dispatch_stays_in_the_history(env: _Fixture) -> None:
    """A promoter who clicked and got nothing should see why."""
    student = await _student(env)
    env.agent.unavailable = True

    with pytest.raises(AgentUnavailableError):
        await env.actions.trigger(
            PROMOTOR, student.id, action_type=ActionType.PROPOSE_TOPIC, token=TOKEN
        )

    actions = await env.actions.list_actions(PROMOTOR, student.id)
    assert len(actions) == 1
    assert actions[0].status is ActionStatus.FAILED
    assert "connection refused" in (actions[0].error or "")


# ---------- polling ----------


async def test_polling_copies_the_agents_view(env: _Fixture) -> None:
    student = await _student(env)
    action = await env.actions.trigger(
        PROMOTOR, student.id, action_type=ActionType.PROPOSE_TOPIC, token=TOKEN
    )
    env.agent.completes_with(topic_payload("Instytucje a wzrost"))

    refreshed = await env.actions.get_action(PROMOTOR, student.id, action.id, TOKEN)

    assert refreshed.status is ActionStatus.COMPLETED
    assert refreshed.proposed_topics()[0]["title"] == "Instytucje a wzrost"


async def test_finished_action_is_not_polled_again(env: _Fixture) -> None:
    """Once terminal, the answer is ours — the agent is not asked twice."""
    student = await _student(env)
    action = await env.actions.trigger(
        PROMOTOR, student.id, action_type=ActionType.PROPOSE_TOPIC, token=TOKEN
    )
    env.agent.completes_with(topic_payload("Instytucje a wzrost"))
    await env.actions.get_action(PROMOTOR, student.id, action.id, TOKEN)

    env.agent.polls.clear()
    await env.actions.get_action(PROMOTOR, student.id, action.id, TOKEN)

    assert env.agent.polls == []


async def test_polling_survives_an_unavailable_agent(env: _Fixture) -> None:
    """A restarting agent must not turn a poll into an error."""
    student = await _student(env)
    action = await env.actions.trigger(
        PROMOTOR, student.id, action_type=ActionType.PROPOSE_TOPIC, token=TOKEN
    )
    env.agent.unavailable = True

    refreshed = await env.actions.get_action(PROMOTOR, student.id, action.id, TOKEN)

    assert refreshed.status is ActionStatus.PENDING


async def test_agent_failure_is_recorded(env: _Fixture) -> None:
    student = await _student(env)
    action = await env.actions.trigger(
        PROMOTOR, student.id, action_type=ActionType.PROPOSE_TOPIC, token=TOKEN
    )
    env.agent.fails_with("Ollama unreachable")

    refreshed = await env.actions.get_action(PROMOTOR, student.id, action.id, TOKEN)

    assert refreshed.status is ActionStatus.FAILED
    assert refreshed.error == "Ollama unreachable"


async def test_action_of_another_student_is_not_found(env: _Fixture) -> None:
    mine = await _student(env)
    theirs = await _student(env)
    action = await env.actions.trigger(
        PROMOTOR, theirs.id, action_type=ActionType.PROPOSE_TOPIC, token=TOKEN
    )

    with pytest.raises(ActionNotFoundError):
        await env.actions.get_action(PROMOTOR, mine.id, action.id, TOKEN)


async def test_list_filters_by_action_type(env: _Fixture) -> None:
    student = await _student(env)
    await env.actions.trigger(
        PROMOTOR, student.id, action_type=ActionType.PROPOSE_TOPIC, token=TOKEN
    )

    assert (
        len(
            await env.actions.list_actions(
                PROMOTOR, student.id, ActionType.PROPOSE_TOPIC
            )
        )
        == 1
    )
    assert (
        await env.actions.list_actions(PROMOTOR, student.id, ActionType.GENERATE_REVIEW)
        == []
    )


# ---------- accept ----------


async def _completed_action(
    env: _Fixture, student_id: uuid.UUID, *titles: str
) -> uuid.UUID:
    action = await env.actions.trigger(
        PROMOTOR, student_id, action_type=ActionType.PROPOSE_TOPIC, token=TOKEN
    )
    env.agent.completes_with(topic_payload(*titles))
    await env.actions.get_action(PROMOTOR, student_id, action.id, TOKEN)
    return action.id


async def test_accepting_a_proposal_sets_the_topic(env: _Fixture) -> None:
    """The model proposes, the promoter decides — and only that is stored."""
    student = await _student(env)
    action_id = await _completed_action(
        env, student.id, "Instytucje a wzrost", "Kapitał społeczny"
    )

    accepted = await env.actions.accept(
        PROMOTOR, student.id, action_id, topic_index=1
    )

    assert accepted.accepted is True
    assert accepted.accepted_at is not None
    updated = await env.students.get(PROMOTOR, student.id)
    assert updated.current_topic == "Kapitał społeczny"
    assert updated.current_topic_set_at is not None


async def test_accepting_twice_is_rejected(env: _Fixture) -> None:
    student = await _student(env)
    action_id = await _completed_action(env, student.id, "Instytucje a wzrost")
    await env.actions.accept(PROMOTOR, student.id, action_id)

    with pytest.raises(ValueError, match="cannot be accepted"):
        await env.actions.accept(PROMOTOR, student.id, action_id)


async def test_unfinished_action_cannot_be_accepted(env: _Fixture) -> None:
    student = await _student(env)
    action = await env.actions.trigger(
        PROMOTOR, student.id, action_type=ActionType.PROPOSE_TOPIC, token=TOKEN
    )

    with pytest.raises(ValueError, match="cannot be accepted"):
        await env.actions.accept(PROMOTOR, student.id, action.id)


async def test_unknown_topic_index_changes_nothing(env: _Fixture) -> None:
    """Validation happens before any write — no half-accepted action."""
    student = await _student(env)
    action_id = await _completed_action(env, student.id, "Instytucje a wzrost")

    with pytest.raises(ValueError, match="No proposed topic"):
        await env.actions.accept(PROMOTOR, student.id, action_id, topic_index=5)

    assert (await env.students.get(PROMOTOR, student.id)).current_topic is None
    actions = await env.actions.list_actions(PROMOTOR, student.id)
    assert actions[0].accepted is False
