"""The demo seed: every fixture loads, and the roster comes out as described."""

from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.seed_demo import load, reset_roster, seed_roster, shift_days
from src.mentoring.infrastructure.orm import (
    DraftFileModel,
    MeetingNoteModel,
    StudentModel,
    ThesisDraftModel,
)
from tests.test_mentoring.conftest import ADMIN_EMAIL, PROMOTOR_EMAIL, PROMOTOR_UUID
from tests.test_mentoring.fakes import FakeAgentClient


async def _count(session: AsyncSession, model: type) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar_one()


def test_every_student_has_a_history_and_all_but_one_a_thesis() -> None:
    students = load()

    assert len(students) == 7
    assert all(any(e.note for e in s.timeline) for s in students)
    without_thesis = [s for s in students if not any(e.draft for e in s.timeline)]
    assert [s.full_name for s in without_thesis] == ["Kazimierz Pawlak"]
    assert without_thesis[0].topic is None


async def test_seed_fills_the_promoters_roster(db_session: AsyncSession) -> None:
    assert await seed_roster(db_session, PROMOTOR_EMAIL, load()) == 0

    students = (await db_session.execute(select(StudentModel))).scalars().all()
    assert len(students) == 7
    assert {s.promotor_id for s in students} == {PROMOTOR_UUID}
    assert await _count(db_session, MeetingNoteModel) == 21
    # Six theses, one of them in two versions.
    assert await _count(db_session, ThesisDraftModel) == 7


async def test_two_versions_are_numbered_in_upload_order(
    db_session: AsyncSession,
) -> None:
    await seed_roster(db_session, PROMOTOR_EMAIL, load())

    student = (
        await db_session.execute(
            select(StudentModel).where(StudentModel.full_name == "Adam Miauczyński")
        )
    ).scalar_one()
    drafts = (
        (
            await db_session.execute(
                select(ThesisDraftModel)
                .where(ThesisDraftModel.student_id == student.id)
                .order_by(ThesisDraftModel.version_number)
            )
        )
        .scalars()
        .all()
    )
    assert [(d.version_number, d.filename) for d in drafts] == [
        (1, "miauczynski_praca_magisterska_v1.docx"),
        (2, "miauczynski_praca_magisterska_v2.docx"),
    ]
    assert len(drafts[0].text or "") < len(drafts[1].text or "")


async def test_everything_is_dated_as_the_timeline_says(
    db_session: AsyncSession,
) -> None:
    await seed_roster(db_session, PROMOTOR_EMAIL, load())

    student = (
        await db_session.execute(
            select(StudentModel).where(StudentModel.full_name == "Adam Miauczyński")
        )
    ).scalar_one()
    drafts = (
        (
            await db_session.execute(
                select(ThesisDraftModel)
                .where(ThesisDraftModel.student_id == student.id)
                .order_by(ThesisDraftModel.version_number)
            )
        )
        .scalars()
        .all()
    )
    # The student and the topic from the first meeting, each version from its
    # own entry — not from the moment the seed ran.
    assert student.created_at.date() == date(2025, 10, 14)
    assert student.current_topic_set_at is not None
    assert student.current_topic_set_at.date() == date(2025, 10, 14)
    assert [d.created_at.date() for d in drafts] == [
        date(2026, 2, 10),
        date(2026, 5, 5),
    ]


async def test_the_good_thesis_is_accepted_as_final(db_session: AsyncSession) -> None:
    await seed_roster(db_session, PROMOTOR_EMAIL, load())

    students = (await db_session.execute(select(StudentModel))).scalars().all()
    accepted = [s for s in students if s.accepted_draft_id is not None]
    assert [s.full_name for s in accepted] == ["Stanisław Anioł"]
    draft = (
        await db_session.execute(
            select(ThesisDraftModel).where(
                ThesisDraftModel.id == accepted[0].accepted_draft_id
            )
        )
    ).scalar_one()
    assert draft.student_id == accepted[0].id
    assert accepted[0].draft_accepted_at is not None
    assert accepted[0].draft_accepted_at.date() == date(2026, 5, 28)


@pytest.mark.parametrize(
    ("latest", "as_of", "days_before"),
    [
        (date(2026, 6, 9), date(2026, 10, 5), 6),
        (date(2026, 6, 9), date(2026, 6, 16), 7),
        (date(2026, 6, 9), date(2026, 6, 17), 1),
        # A timeline that ends after `as_of` is moved back, not left ahead.
        (date(2026, 6, 9), date(2026, 6, 9), 7),
    ],
)
def test_the_shift_is_whole_weeks_and_ends_in_the_week_before(
    latest: date, as_of: date, days_before: int
) -> None:
    shift = shift_days(latest, as_of)

    assert shift % 7 == 0
    assert (as_of - latest).days - shift == days_before


def test_as_of_moves_every_entry_by_the_same_number_of_days() -> None:
    written = load()
    moved = load(as_of=date(2026, 10, 5))

    shifts = {
        (m.at - w.at).days
        for was, now in zip(written, moved, strict=True)
        for w, m in zip(was.timeline, now.timeline, strict=True)
    }
    assert shifts == {112}
    latest = max(e.at for s in moved for e in s.timeline)
    assert latest.date() == date(2026, 9, 29)


async def test_running_it_again_adds_nothing(db_session: AsyncSession) -> None:
    await seed_roster(db_session, PROMOTOR_EMAIL, load())
    assert await seed_roster(db_session, PROMOTOR_EMAIL, load()) == 0

    assert await _count(db_session, StudentModel) == 7
    assert await _count(db_session, ThesisDraftModel) == 7


@pytest.mark.parametrize("email", [ADMIN_EMAIL, "nobody@example.com"])
async def test_students_go_only_to_an_existing_promoter(
    db_session: AsyncSession, email: str
) -> None:
    assert await seed_roster(db_session, email, load()) == 1
    assert await _count(db_session, StudentModel) == 0


def _someone_else(promotor_id: object) -> StudentModel:
    return StudentModel(
        promotor_id=promotor_id,
        full_name="Ktoś Inny",
        field_of_study="Ekonomia",
        thesis_type="bachelor",
        status="active",
    )


async def test_reset_deletes_the_demo_students_and_nobody_else(
    db_session: AsyncSession,
) -> None:
    await seed_roster(db_session, PROMOTOR_EMAIL, load())
    db_session.add(_someone_else(PROMOTOR_UUID))
    await db_session.commit()
    agent = FakeAgentClient()

    assert await reset_roster(db_session, PROMOTOR_EMAIL, load(), agent) == 0

    left = (await db_session.execute(select(StudentModel))).scalars().all()
    assert [s.full_name for s in left] == ["Ktoś Inny"]
    assert len(agent.deleted_students) == 7
    # Nothing of theirs is stranded: notes, versions and the files themselves.
    assert await _count(db_session, MeetingNoteModel) == 0
    assert await _count(db_session, ThesisDraftModel) == 0
    assert await _count(db_session, DraftFileModel) == 0


async def test_reset_then_seed_gives_the_same_roster(db_session: AsyncSession) -> None:
    await seed_roster(db_session, PROMOTOR_EMAIL, load())
    await reset_roster(db_session, PROMOTOR_EMAIL, load(), FakeAgentClient())
    assert await seed_roster(db_session, PROMOTOR_EMAIL, load()) == 0

    assert await _count(db_session, StudentModel) == 7
    assert await _count(db_session, MeetingNoteModel) == 21
    assert await _count(db_session, ThesisDraftModel) == 7
    assert await _count(db_session, DraftFileModel) == 7


async def test_reset_deletes_nothing_without_the_agent(
    db_session: AsyncSession,
) -> None:
    await seed_roster(db_session, PROMOTOR_EMAIL, load())
    agent = FakeAgentClient()
    agent.unavailable = True

    assert await reset_roster(db_session, PROMOTOR_EMAIL, load(), agent) == 1

    assert await _count(db_session, StudentModel) == 7
    assert await _count(db_session, ThesisDraftModel) == 7


def test_only_narrows_the_fixtures_to_the_named_ones() -> None:
    assert [s.full_name for s in load(only=["06_adamczewski"])] == [
        "Jan Paweł Adamczewski"
    ]
    with pytest.raises(ValueError, match="No such fixture"):
        load(only=["99_nikt"])


async def test_resetting_one_student_leaves_the_others_as_they_were(
    db_session: AsyncSession,
) -> None:
    await seed_roster(db_session, PROMOTOR_EMAIL, load())
    before = {
        s.full_name: s.id
        for s in (await db_session.execute(select(StudentModel))).scalars().all()
    }
    one = load(only=["06_adamczewski"])
    agent = FakeAgentClient()

    await reset_roster(db_session, PROMOTOR_EMAIL, one, agent)
    await seed_roster(db_session, PROMOTOR_EMAIL, one)

    after = {
        s.full_name: s.id
        for s in (await db_session.execute(select(StudentModel))).scalars().all()
    }
    assert len(agent.deleted_students) == 1
    changed = {name for name in before if before[name] != after[name]}
    assert changed == {"Jan Paweł Adamczewski"}
    assert await _count(db_session, StudentModel) == 7
