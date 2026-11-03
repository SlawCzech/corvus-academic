"""Unit tests for ActionService — the AI action lifecycle inside `app`.

The agent is faked: what matters here is that the attempt is recorded before
dispatch, that a promoter only ever sees their own students' actions, and
that accepting a proposal is what changes the student.
"""

import json
import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.mentoring.application.action_service import ActionService
from src.mentoring.application.agent_client import BYOK
from src.mentoring.application.draft_service import DraftService
from src.mentoring.application.exceptions import (
    ActionNotFoundError,
    AgentUnavailableError,
    MissingContextError,
    ProviderKeyMissingError,
    StudentNotFoundError,
)
from src.mentoring.application.student_service import Caller, StudentService
from src.mentoring.domain.action import ActionStatus, ActionType
from src.mentoring.domain.student import Student, ThesisType
from src.mentoring.infrastructure.orm import AgentActionModel, Base, DraftFileModel
from src.mentoring.infrastructure.repositories import (
    AgentActionRepository,
    MeetingNoteRepository,
    StudentRepository,
    ThesisDraftRepository,
)
from src.shared.sql_file_store import SqlFileStore
from tests.test_mentoring.fakes import (
    FakeAgentClient,
    FakeGuidelineSource,
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
    """The collaborators a test needs, wired to one SQLite session."""

    def __init__(
        self,
        students: StudentService,
        actions: ActionService,
        drafts: DraftService,
        agent: FakeAgentClient,
        guidelines: FakeGuidelineSource,
        session: AsyncSession,
    ) -> None:
        self.students = students
        self.actions = actions
        self.drafts = drafts
        self.agent = agent
        self.guidelines = guidelines
        self.session = session


@pytest.fixture
async def env() -> AsyncGenerator[_Fixture, None]:
    engine = create_async_engine(_SQLITE_URL, execution_options=_SCHEMA_TRANSLATE)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        guidelines = FakeGuidelineSource()
        students = StudentService(
            StudentRepository(session), MeetingNoteRepository(session), guidelines
        )
        agent = FakeAgentClient()
        drafts = ThesisDraftRepository(session)
        yield _Fixture(
            students,
            ActionService(
                students, AgentActionRepository(session), drafts, agent, guidelines
            ),
            DraftService(students, drafts, SqlFileStore(session, DraftFileModel)),
            agent,
            guidelines,
            session,
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


async def test_trigger_passes_review_tone_to_the_review_context(
    env: _Fixture,
) -> None:
    """`review_tone` only means anything to generate_review's own context."""
    student = await _student(env)
    await env.drafts.upload(
        PROMOTOR, student.id, filename="praca.docx", data=docx_bytes()
    )

    await env.actions.trigger(
        PROMOTOR,
        student.id,
        action_type=ActionType.GENERATE_REVIEW,
        token=TOKEN,
        review_tone="enthusiastic",
    )

    context = env.agent.submitted[0]["context"]
    assert context["review_tone"] == "enthusiastic"


async def test_trigger_defaults_review_tone_to_auto(env: _Fixture) -> None:
    student = await _student(env)
    await env.drafts.upload(
        PROMOTOR, student.id, filename="praca.docx", data=docx_bytes()
    )

    await env.actions.trigger(
        PROMOTOR, student.id, action_type=ActionType.GENERATE_REVIEW, token=TOKEN
    )

    assert env.agent.submitted[0]["context"]["review_tone"] == "auto"


async def test_review_is_judged_against_the_chosen_guideline_set(
    env: _Fixture,
) -> None:
    """The rubric in force goes to the agent, and the action records its version."""
    student = await _student(env)
    set_id = uuid.uuid4()
    version_id = env.guidelines.publish(set_id, "bachelor", "## UE Katowice v2")
    await env.students.update(
        PROMOTOR, student.id, guideline_set_id=set_id, set_guidelines=True
    )
    await env.drafts.upload(
        PROMOTOR, student.id, filename="praca.docx", data=docx_bytes()
    )

    action = await env.actions.trigger(
        PROMOTOR, student.id, action_type=ActionType.GENERATE_REVIEW, token=TOKEN
    )

    assert env.agent.submitted[0]["context"]["guidelines"] == "## UE Katowice v2"
    record = await env.actions.list_actions(PROMOTOR, student.id, TOKEN)
    assert record[0].id == action.id
    stored = await _input_ref(env, student.id)
    assert stored["guideline_version_id"] == str(version_id)


@pytest.mark.parametrize(
    "action_type", [ActionType.GENERATE_REVIEW, ActionType.TRIAL_REVIEW]
)
async def test_both_reviews_carry_the_thresholds_of_the_set(
    env: _Fixture, action_type: ActionType
) -> None:
    student = await _student(env)
    set_id = uuid.uuid4()
    env.guidelines.publish(set_id, "bachelor", "## v1", {"min_sources": 25})
    await env.students.update(
        PROMOTOR, student.id, guideline_set_id=set_id, set_guidelines=True
    )
    await env.drafts.upload(
        PROMOTOR, student.id, filename="praca.docx", data=docx_bytes()
    )

    await env.actions.trigger(
        PROMOTOR, student.id, action_type=action_type, token=TOKEN
    )

    assert env.agent.submitted[0]["context"]["thresholds"] == {"min_sources": 25}


async def test_without_a_guideline_set_the_agent_uses_its_own(env: _Fixture) -> None:
    student = await _student(env)
    await env.drafts.upload(
        PROMOTOR, student.id, filename="praca.docx", data=docx_bytes()
    )

    await env.actions.trigger(
        PROMOTOR,
        student.id,
        action_type=ActionType.EVALUATE_METHODOLOGY,
        token=TOKEN,
    )

    assert "guidelines" not in env.agent.submitted[0]["context"]
    assert "guideline_version_id" not in await _input_ref(env, student.id)


async def test_a_guideline_set_for_another_thesis_type_is_refused(
    env: _Fixture,
) -> None:
    student = await _student(env)
    set_id = uuid.uuid4()
    env.guidelines.publish(set_id, "master_article", "## Magisterskie")

    with pytest.raises(ValueError, match="master_article"):
        await env.students.update(
            PROMOTOR, student.id, guideline_set_id=set_id, set_guidelines=True
        )


async def test_an_unknown_guideline_set_is_refused(env: _Fixture) -> None:
    student = await _student(env)

    with pytest.raises(ValueError, match="not found"):
        await env.students.update(
            PROMOTOR, student.id, guideline_set_id=uuid.uuid4(), set_guidelines=True
        )


async def test_the_guideline_choice_can_be_cleared(env: _Fixture) -> None:
    student = await _student(env)
    set_id = uuid.uuid4()
    env.guidelines.publish(set_id, "bachelor", "## v1")
    await env.students.update(
        PROMOTOR, student.id, guideline_set_id=set_id, set_guidelines=True
    )

    cleared = await env.students.update(
        PROMOTOR, student.id, guideline_set_id=None, set_guidelines=True
    )
    kept = await env.students.update(PROMOTOR, student.id, current_topic="Temat")

    assert cleared.guideline_set_id is None
    assert kept.guideline_set_id is None


async def test_a_new_thesis_type_drops_the_guideline_choice(env: _Fixture) -> None:
    student = await _student(env)
    set_id = uuid.uuid4()
    env.guidelines.publish(set_id, "bachelor", "## Licencjackie")
    await env.students.update(
        PROMOTOR, student.id, guideline_set_id=set_id, set_guidelines=True
    )

    changed = await env.students.update(
        PROMOTOR, student.id, thesis_type=ThesisType.MASTER_ARTICLE
    )

    assert changed.guideline_set_id is None


async def test_a_guideline_set_is_checked_against_the_new_thesis_type(
    env: _Fixture,
) -> None:
    student = await _student(env)
    set_id = uuid.uuid4()
    env.guidelines.publish(set_id, "master_article", "## Magisterskie")

    changed = await env.students.update(
        PROMOTOR,
        student.id,
        thesis_type=ThesisType.MASTER_ARTICLE,
        guideline_set_id=set_id,
        set_guidelines=True,
    )

    assert changed.thesis_type is ThesisType.MASTER_ARTICLE
    assert changed.guideline_set_id == set_id


async def _input_ref(env: _Fixture, student_id: uuid.UUID) -> dict[str, object]:
    """The provenance stored on the student's newest action."""
    row = (
        (
            await env.session.execute(
                select(AgentActionModel)
                .where(AgentActionModel.student_id == student_id)
                .order_by(AgentActionModel.created_at.desc())
            )
        )
        .scalars()
        .first()
    )
    assert row is not None
    return dict(row.input_ref or {})


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
    assert await env.actions.list_actions(PROMOTOR, student.id, TOKEN) == []
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

    actions = await env.actions.list_actions(PROMOTOR, student.id, TOKEN)
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


async def test_listing_picks_up_a_result_nobody_polled_for(env: _Fixture) -> None:
    """A reloaded page only asks for the list — the result must still land."""
    student = await _student(env)
    action = await env.actions.trigger(
        PROMOTOR, student.id, action_type=ActionType.PROPOSE_TOPIC, token=TOKEN
    )
    env.agent.completes_with(topic_payload("Instytucje a wzrost"))

    listed = await env.actions.list_actions(PROMOTOR, student.id, TOKEN)

    assert listed[0].id == action.id
    assert listed[0].status is ActionStatus.COMPLETED
    assert listed[0].proposed_topics()[0]["title"] == "Instytucje a wzrost"
    stored = await env.actions.get_action(PROMOTOR, student.id, action.id, TOKEN)
    assert stored.status is ActionStatus.COMPLETED


async def test_listing_does_not_poll_finished_actions(env: _Fixture) -> None:
    student = await _student(env)
    await _completed_action(env, student.id, "Instytucje a wzrost")
    env.agent.polls.clear()

    await env.actions.list_actions(PROMOTOR, student.id, TOKEN)

    assert env.agent.polls == []


async def test_listing_survives_an_unavailable_agent(env: _Fixture) -> None:
    student = await _student(env)
    await env.actions.trigger(
        PROMOTOR, student.id, action_type=ActionType.PROPOSE_TOPIC, token=TOKEN
    )
    env.agent.unavailable = True

    listed = await env.actions.list_actions(PROMOTOR, student.id, TOKEN)

    assert listed[0].status is ActionStatus.PENDING


async def test_cancel_stops_the_run_and_marks_the_action(env: _Fixture) -> None:
    student = await _student(env)
    action = await env.actions.trigger(
        PROMOTOR, student.id, action_type=ActionType.PROPOSE_TOPIC, token=TOKEN
    )

    cancelled = await env.actions.cancel(PROMOTOR, student.id, action.id, TOKEN)

    assert cancelled.status is ActionStatus.CANCELLED
    assert env.agent.cancelled == ["task-1"]
    stored = await env.actions.get_action(PROMOTOR, student.id, action.id, TOKEN)
    assert stored.status is ActionStatus.CANCELLED


async def test_cancel_holds_without_the_agent(env: _Fixture) -> None:
    """A run dead long ago is cleared even when the agent cannot be told."""
    student = await _student(env)
    action = await env.actions.trigger(
        PROMOTOR, student.id, action_type=ActionType.PROPOSE_TOPIC, token=TOKEN
    )
    env.agent.unavailable = True

    cancelled = await env.actions.cancel(PROMOTOR, student.id, action.id, TOKEN)

    assert cancelled.status is ActionStatus.CANCELLED


async def test_a_finished_action_cannot_be_cancelled(env: _Fixture) -> None:
    student = await _student(env)
    action_id = await _completed_action(env, student.id, "Instytucje a wzrost")

    with pytest.raises(ValueError, match="cannot be cancelled"):
        await env.actions.cancel(PROMOTOR, student.id, action_id, TOKEN)
    assert env.agent.cancelled == []


async def test_a_cancelled_action_is_not_polled(env: _Fixture) -> None:
    student = await _student(env)
    action = await env.actions.trigger(
        PROMOTOR, student.id, action_type=ActionType.PROPOSE_TOPIC, token=TOKEN
    )
    await env.actions.cancel(PROMOTOR, student.id, action.id, TOKEN)
    env.agent.completes_with(topic_payload("Za późno"))
    env.agent.polls.clear()

    listed = await env.actions.list_actions(PROMOTOR, student.id, TOKEN)

    assert listed[0].status is ActionStatus.CANCELLED
    assert env.agent.polls == []


async def test_in_progress_drops_what_the_agent_finished(env: _Fixture) -> None:
    student = await _student(env)
    await env.actions.trigger(
        PROMOTOR, student.id, action_type=ActionType.PROPOSE_TOPIC, token=TOKEN
    )
    running = await env.actions.in_progress(PROMOTOR, TOKEN)
    env.agent.completes_with(topic_payload("Instytucje a wzrost"))

    after = await env.actions.in_progress(PROMOTOR, TOKEN)

    assert [a.student_name for a in running] == ["Jan Kowalski"]
    assert after == []


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
                PROMOTOR, student.id, TOKEN, ActionType.PROPOSE_TOPIC
            )
        )
        == 1
    )
    assert (
        await env.actions.list_actions(
            PROMOTOR, student.id, TOKEN, ActionType.GENERATE_REVIEW
        )
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

    accepted = await env.actions.accept(PROMOTOR, student.id, action_id, topic_index=1)

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
    actions = await env.actions.list_actions(PROMOTOR, student.id, TOKEN)
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
    stored = (await env.actions.list_actions(PROMOTOR, student.id, TOKEN))[0]
    assert stored.id == action.id


async def test_progress_check_sends_only_the_notes_between_the_versions(
    env: _Fixture,
) -> None:
    student = await _student(env)

    async def note(content: str) -> uuid.UUID:
        made = await env.students.add_meeting_note(PROMOTOR, student.id, content)
        return made.id

    await note("Przed pierwszą wersją")
    await env.drafts.upload(
        PROMOTOR, student.id, filename="v1.docx", data=docx_bytes("Wersja pierwsza")
    )
    between = await note("Uzasadnić dobór próby")
    await env.drafts.upload(
        PROMOTOR, student.id, filename="v2.docx", data=docx_bytes("Wersja druga")
    )
    await note("Po drugiej wersji")

    await env.actions.trigger(
        PROMOTOR, student.id, action_type=ActionType.CHECK_PROGRESS, token=TOKEN
    )

    context = env.agent.submitted[0]["context"]
    assert context["meeting_notes"] == ["Uzasadnić dobór próby"]
    assert (await _input_ref(env, student.id))["note_ids"] == [str(between)]


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


async def _keys(provider: str) -> BYOK | None:
    """A promoter holding a Claude key and no other."""
    if provider == "claude":
        return BYOK(provider="claude", api_key="sk-user-key")
    return None


async def test_the_users_key_is_forwarded_to_the_agent(env: _Fixture) -> None:
    student = await _student(env)

    action = await env.actions.trigger(
        PROMOTOR,
        student.id,
        action_type=ActionType.PROPOSE_TOPIC,
        token=TOKEN,
        provider="claude",
        keys=_keys,
    )

    sent = env.agent.submitted[0]["byok"]
    assert sent is not None
    assert sent.provider == "claude"
    assert action.provider == "claude"


async def test_a_provider_without_a_key_is_refused_before_anything_is_recorded(
    env: _Fixture,
) -> None:
    student = await _student(env)

    with pytest.raises(ProviderKeyMissingError):
        await env.actions.trigger(
            PROMOTOR,
            student.id,
            action_type=ActionType.PROPOSE_TOPIC,
            token=TOKEN,
            provider="openai",
            keys=_keys,
        )

    assert env.agent.submitted == []
    assert await env.actions.list_actions(PROMOTOR, student.id, TOKEN) == []


async def test_a_held_key_is_not_used_when_no_provider_is_asked_for(
    env: _Fixture,
) -> None:
    student = await _student(env)

    action = await env.actions.trigger(
        PROMOTOR,
        student.id,
        action_type=ActionType.PROPOSE_TOPIC,
        token=TOKEN,
        keys=_keys,
    )

    assert env.agent.submitted[0]["byok"] is None
    assert action.provider is None


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
        provider="claude",
        keys=_keys,
    )

    stored = (await env.actions.list_actions(PROMOTOR, student.id, TOKEN))[0]
    assert stored.id == action.id
    assert "sk-user-key" not in json.dumps(
        {"detail": stored.detail, "output": stored.output, "error": stored.error},
        default=str,
    )


async def test_a_failure_the_promoter_can_fix_keeps_its_code(env: _Fixture) -> None:
    student = await _student(env)
    action = await env.actions.trigger(
        PROMOTOR, student.id, action_type=ActionType.PROPOSE_TOPIC, token=TOKEN
    )
    env.agent.fails_with("anthropic: credit balance too low", "provider_no_credits")

    refreshed = await env.actions.get_action(PROMOTOR, student.id, action.id, TOKEN)

    assert refreshed.status is ActionStatus.FAILED
    assert refreshed.error_code == "provider_no_credits"


async def test_the_tokens_an_action_spent_are_kept_with_it(env: _Fixture) -> None:
    """Copied once the agent reports them, and still there when it is gone."""
    student = await _student(env)
    action = await env.actions.trigger(
        PROMOTOR, student.id, action_type=ActionType.PROPOSE_TOPIC, token=TOKEN
    )
    usage = {
        "input_tokens": 12000,
        "output_tokens": 800,
        "total_tokens": 12800,
        "by_model": {
            "claude-sonnet-5-5": {
                "input_tokens": 12000,
                "output_tokens": 800,
                "total_tokens": 12800,
            }
        },
    }
    env.agent.completes_with(topic_payload("Instytucje"), usage=usage)

    refreshed = await env.actions.get_action(PROMOTOR, student.id, action.id, TOKEN)
    assert refreshed.usage == usage

    env.agent.unavailable = True
    stored = (await env.actions.list_actions(PROMOTOR, student.id, TOKEN))[0]
    assert stored.usage == usage
