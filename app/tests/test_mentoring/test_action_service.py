"""Unit tests for ActionService — the AI action lifecycle inside `app`.

The agent is faked: what matters here is that the attempt is recorded before
dispatch, that a promoter only ever sees their own students' actions, and
that accepting a proposal is what changes the student.
"""

import json
import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.mentoring.application.action_service import (
    ActionNotFoundError,
    ActionService,
)
from src.mentoring.application.agent_client import BYOK, AgentUnavailableError
from src.mentoring.application.context import MissingContextError
from src.mentoring.application.draft_service import DraftService
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
    ThesisDraftRepository,
)
from tests.test_mentoring.fakes import (
    FakeAgentClient,
    docx_bytes,
    note_payload,
    topic_payload,
)

_SQLITE_URL = "sqlite+aiosqlite:///:memory:"
_SCHEMA_TRANSLATE = {"schema_translate_map": {"mentoring": None}}

PROMOTOR = Caller(user_id=uuid.UUID("00000000-0000-0000-0000-0000000000a1"))
OTHER = Caller(user_id=uuid.UUID("00000000-0000-0000-0000-0000000000a2"))
TOKEN = "header.payload.signature"  # noqa: S105


class _Fixture:
    """The three collaborators a test needs, wired to one SQLite session."""

    def __init__(
        self,
        students: StudentService,
        actions: ActionService,
        drafts: DraftService,
        agent: FakeAgentClient,
    ) -> None:
        self.students = students
        self.actions = actions
        self.drafts = drafts
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
        drafts = ThesisDraftRepository(session)
        yield _Fixture(
            students,
            ActionService(students, AgentActionRepository(session), drafts, agent),
            DraftService(students, drafts),
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


async def test_action_needing_a_draft_is_refused_without_one(
    env: _Fixture,
) -> None:
    """Asking about a thesis nobody uploaded is a state problem, not a job."""
    student = await _student(env)

    with pytest.raises(MissingContextError):
        await env.actions.trigger(
            PROMOTOR,
            student.id,
            action_type=ActionType.DEFENCE_QUESTIONS,
            token=TOKEN,
        )
    assert await env.actions.list_actions(PROMOTOR, student.id) == []
    assert env.agent.submitted == []


async def test_progress_check_needs_two_versions(env: _Fixture) -> None:
    student = await _student(env)
    await env.drafts.upload(
        PROMOTOR, student.id, filename="praca.docx", data=docx_bytes()
    )

    with pytest.raises(MissingContextError, match="two uploaded versions"):
        await env.actions.trigger(
            PROMOTOR, student.id, action_type=ActionType.CHECK_PROGRESS, token=TOKEN
        )


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


async def test_accepting_a_drafted_note_saves_it_with_its_provenance(
    env: _Fixture,
) -> None:
    """An AI-drafted note becomes a real note that still says where it came from."""
    student = await _student(env)
    await env.students.add_meeting_note(PROMOTOR, student.id, content="Poprzednie")
    action = await env.actions.trigger(
        PROMOTOR,
        student.id,
        action_type=ActionType.DRAFT_MEETING_NOTE,
        token=TOKEN,
        detail="rozdział 2, dobór próby, termin 15.03",
    )
    env.agent.completes_with(note_payload("Omówiliśmy zakres rozdziału 2."))
    await env.actions.get_action(PROMOTOR, student.id, action.id, TOKEN)

    await env.actions.accept(PROMOTOR, student.id, action.id)

    notes = await env.students.list_meeting_notes(PROMOTOR, student.id)
    drafted = [n for n in notes if n.is_ai_drafted]
    assert len(drafted) == 1
    assert drafted[0].content == "Omówiliśmy zakres rozdziału 2."
    assert drafted[0].source_action_id == action.id


async def test_meeting_note_action_needs_rough_notes(env: _Fixture) -> None:
    """The action writes up what the promoter jotted down; it invents nothing."""
    student = await _student(env)

    with pytest.raises(MissingContextError, match="Rough notes"):
        await env.actions.trigger(
            PROMOTOR,
            student.id,
            action_type=ActionType.DRAFT_MEETING_NOTE,
            token=TOKEN,
        )


async def test_defence_questions_use_the_latest_version(env: _Fixture) -> None:
    """Only the newest draft is sent — the committee asks about what was handed in."""
    student = await _student(env)
    await env.drafts.upload(
        PROMOTOR, student.id, filename="v1.docx", data=docx_bytes("Wersja pierwsza")
    )
    await env.drafts.upload(
        PROMOTOR, student.id, filename="v2.docx", data=docx_bytes("Wersja druga")
    )

    await env.actions.trigger(
        PROMOTOR, student.id, action_type=ActionType.DEFENCE_QUESTIONS, token=TOKEN
    )

    context = env.agent.submitted[0]["context"]
    assert "Wersja druga" in context["text"]
    assert "Wersja pierwsza" not in context["text"]
    assert context["version_number"] == 2


async def test_progress_check_sends_both_versions(env: _Fixture) -> None:
    student = await _student(env)
    await env.drafts.upload(
        PROMOTOR, student.id, filename="v1.docx", data=docx_bytes("Wersja pierwsza")
    )
    await env.drafts.upload(
        PROMOTOR, student.id, filename="v2.docx", data=docx_bytes("Wersja druga")
    )

    action = await env.actions.trigger(
        PROMOTOR, student.id, action_type=ActionType.CHECK_PROGRESS, token=TOKEN
    )

    context = env.agent.submitted[0]["context"]
    assert "Wersja druga" in context["current_text"]
    assert "Wersja pierwsza" in context["previous_text"]
    assert (context["current_version"], context["previous_version"]) == (2, 1)
    # Provenance: which rows fed the prompt, by id — never the text itself.
    stored = (await env.actions.list_actions(PROMOTOR, student.id))[0]
    assert stored.id == action.id


async def test_review_context_carries_the_student_as_metadata(env: _Fixture) -> None:
    """The review nodes expect author/title/field, which live on the student."""
    student = await _student(env)
    await env.students.update(PROMOTOR, student.id, current_topic="Instytucje a wzrost")
    await env.drafts.upload(
        PROMOTOR, student.id, filename="praca.docx", data=docx_bytes("Treść pracy")
    )

    await env.actions.trigger(
        PROMOTOR, student.id, action_type=ActionType.GENERATE_REVIEW, token=TOKEN
    )

    metadata = env.agent.submitted[0]["context"]["metadata"]
    assert metadata["author"] == "Jan Kowalski"
    assert metadata["title"] == "Instytucje a wzrost"
    assert metadata["field_of_study"] == "Ekonomia"
    # Guidelines are agent-owned static data — `app` does not ship them.
    assert "guidelines" not in env.agent.submitted[0]["context"]


# ---------- the promoter's own key ----------


async def test_the_users_key_is_forwarded_to_the_agent(env: _Fixture) -> None:
    student = await _student(env)

    await env.actions.trigger(
        PROMOTOR,
        student.id,
        action_type=ActionType.PROPOSE_TOPIC,
        token=TOKEN,
        byok=BYOK(provider="claude", api_key="sk-user-key"),
    )

    sent = env.agent.submitted[0]["byok"]
    assert sent is not None
    assert sent.provider == "claude"


async def test_without_a_key_nothing_is_forwarded(env: _Fixture) -> None:
    """No key means the self-hosted model, which needs none."""
    student = await _student(env)

    await env.actions.trigger(
        PROMOTOR, student.id, action_type=ActionType.PROPOSE_TOPIC, token=TOKEN
    )

    assert env.agent.submitted[0]["byok"] is None


async def test_the_key_is_not_written_to_the_action_row(env: _Fixture) -> None:
    """The row is what the promoter reads back later; it must be clean."""
    student = await _student(env)

    action = await env.actions.trigger(
        PROMOTOR,
        student.id,
        action_type=ActionType.PROPOSE_TOPIC,
        token=TOKEN,
        detail="coś ilościowego",
        byok=BYOK(provider="claude", api_key="sk-user-key"),
    )

    stored = (await env.actions.list_actions(PROMOTOR, student.id))[0]
    assert stored.id == action.id
    assert "sk-user-key" not in json.dumps(
        {"detail": stored.detail, "output": stored.output, "error": stored.error},
        default=str,
    )
