"""Draft acceptance and retention — the policy, the sweep, and the endpoints."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.mentoring.application.draft_service import DraftService
from src.mentoring.application.retention_service import RetentionService
from src.mentoring.application.student_service import Caller, StudentService
from src.mentoring.domain.draft import ThesisDraft
from src.mentoring.domain.retention import RetentionPolicy
from src.mentoring.domain.student import Student, StudentStatus, ThesisType
from src.mentoring.infrastructure.orm import Base, DraftFileModel
from src.mentoring.infrastructure.repositories import (
    MeetingNoteRepository,
    StudentRepository,
    ThesisDraftRepository,
    ThesisFragmentRepository,
)
from src.shared.sql_file_store import SqlFileStore
from tests.test_mentoring.conftest import PROMOTOR_EMAIL, PROMOTOR_PASSWORD, login
from tests.test_mentoring.fakes import docx_bytes

_T0 = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
_POLICY = RetentionPolicy()
_DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _student(**fields: Any) -> Student:  # noqa: ANN401
    return Student(
        id=uuid.uuid4(),
        promotor_id=uuid.uuid4(),
        full_name="Jan Kowalski",
        field_of_study="Ekonomia",
        thesis_type=ThesisType.BACHELOR,
        **fields,
    )


def _draft(version: int, student: Student) -> ThesisDraft:
    return ThesisDraft(
        id=uuid.uuid4(),
        student_id=student.id,
        version_number=version,
        filename=f"v{version}.docx",
        text=f"Wersja {version}",
        pages=1,
        format="docx",
        uploaded_by=student.promotor_id,
    )


# ---------- domain ----------


def test_leaving_active_starts_the_clock_once() -> None:
    student = _student()

    student.change_status(StudentStatus.GRADUATED, at=_T0)
    student.change_status(StudentStatus.ARCHIVED, at=_T0 + timedelta(days=10))

    assert student.closed_at == _T0


def test_returning_to_active_stops_the_clock() -> None:
    student = _student()
    student.change_status(StudentStatus.ARCHIVED, at=_T0)

    student.change_status(StudentStatus.ACTIVE)

    assert student.closed_at is None


def test_a_purged_draft_keeps_its_trace_and_refuses_its_content() -> None:
    draft = _draft(1, _student())

    draft.purge(_T0)

    assert draft.is_purged
    assert draft.char_count == len("Wersja 1")
    assert draft.preview == ""
    with pytest.raises(ValueError, match="purged"):
        _ = draft.content


# ---------- policy ----------


def test_nothing_is_due_for_an_active_student_without_acceptance() -> None:
    student = _student()
    drafts = [_draft(1, student), _draft(2, student)]

    assert _POLICY.drafts_to_purge(student, drafts, _T0 + timedelta(days=999)) == []


@pytest.mark.parametrize(
    ("days_after", "purged_versions"),
    [(13, []), (14, [1]), (15, [1])],
)
def test_non_final_versions_go_fourteen_days_after_acceptance(
    days_after: int, purged_versions: list[int]
) -> None:
    student = _student()
    v1, v2 = _draft(1, student), _draft(2, student)
    student.accept_draft(v2.id, at=_T0)

    due = _POLICY.drafts_to_purge(student, [v1, v2], _T0 + timedelta(days=days_after))

    assert [d.version_number for d in due] == purged_versions


@pytest.mark.parametrize(
    ("days_after", "purged_versions"),
    [(29, []), (30, [1, 2])],
)
def test_every_version_goes_30_days_after_supervision_ends(
    days_after: int, purged_versions: list[int]
) -> None:
    student = _student()
    drafts = [_draft(1, student), _draft(2, student)]
    student.change_status(StudentStatus.GRADUATED, at=_T0)

    due = _POLICY.drafts_to_purge(student, drafts, _T0 + timedelta(days=days_after))

    assert [d.version_number for d in due] == purged_versions


def test_the_earlier_of_the_two_rules_wins() -> None:
    student = _student()
    v1, v2 = _draft(1, student), _draft(2, student)
    student.accept_draft(v2.id, at=_T0)
    student.change_status(StudentStatus.GRADUATED, at=_T0)

    assert _POLICY.purge_due_at(student, v1) == _T0 + timedelta(days=14)
    assert _POLICY.purge_due_at(student, v2) == _T0 + timedelta(days=30)


def test_a_cleared_acceptance_cancels_the_countdown() -> None:
    student = _student()
    v1, v2 = _draft(1, student), _draft(2, student)
    student.accept_draft(v2.id, at=_T0)

    student.clear_draft_acceptance()

    assert _POLICY.drafts_to_purge(student, [v1, v2], _T0 + timedelta(days=60)) == []


def test_an_already_purged_version_is_never_due_again() -> None:
    student = _student()
    draft = _draft(1, student)
    student.change_status(StudentStatus.ARCHIVED, at=_T0)
    draft.purge(_T0)

    assert _POLICY.purge_due_at(student, draft) is None


# ---------- sweep ----------

_CALLER = Caller(user_id=uuid.UUID("00000000-0000-0000-0000-0000000000b1"))


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        execution_options={"schema_translate_map": {"mentoring": None}},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def test_sweep_purges_text_and_file_and_keeps_the_row(
    session: AsyncSession,
) -> None:
    students = StudentService(
        StudentRepository(session), MeetingNoteRepository(session)
    )
    files = SqlFileStore(session, DraftFileModel)
    drafts = DraftService(students, ThesisDraftRepository(session), files)
    student = await students.create(
        _CALLER, full_name="Jan", field_of_study="Ekonomia", thesis_type="bachelor"
    )
    first = await drafts.upload(_CALLER, student.id, "v1.docx", docx_bytes("Jeden"))
    second = await drafts.upload(_CALLER, student.id, "v2.docx", docx_bytes("Dwa"))
    await drafts.accept(_CALLER, student.id, second.draft.id)
    sweep = RetentionService(
        StudentRepository(session),
        ThesisDraftRepository(session),
        ThesisFragmentRepository(session),
        files,
    )

    assert await sweep.sweep(datetime.now(UTC) + timedelta(days=1)) == 0
    purged = await sweep.sweep(datetime.now(UTC) + timedelta(days=31))

    assert purged == 1
    views = {
        v.draft.version_number: v for v in await drafts.list_drafts(_CALLER, student.id)
    }
    old = views[1].draft
    assert old.is_purged and old.text is None and not old.has_file
    assert old.file_sha256 == first.draft.file_sha256
    assert first.draft.file_id is not None
    assert await files.get(first.draft.file_id) is None
    assert views[2].is_accepted and not views[2].draft.is_purged
    # Idempotent: nothing left to purge the second time round.
    assert await sweep.sweep(datetime.now(UTC) + timedelta(days=31)) == 0


# ---------- endpoints ----------


def _setup(client: TestClient) -> tuple[dict[str, str], str, list[str]]:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = client.post(
        "/students",
        json={
            "full_name": "Jan",
            "field_of_study": "Ekonomia",
            "thesis_type": "bachelor",
        },
        headers=headers,
    ).json()["id"]
    draft_ids = [
        client.post(
            f"/students/{student_id}/drafts",
            files={"file": (f"v{n}.docx", docx_bytes(f"Wersja {n}"), _DOCX_TYPE)},
            headers=headers,
        ).json()["id"]
        for n in (1, 2)
    ]
    return headers, student_id, draft_ids


def test_accepting_a_version_schedules_the_others(client: TestClient) -> None:
    headers, student_id, (v1, v2) = _setup(client)

    resp = client.post(f"/students/{student_id}/drafts/{v2}/accept", headers=headers)

    assert resp.status_code == 200
    by_id = {d["id"]: d for d in resp.json()}
    assert by_id[v2]["is_accepted"] is True
    assert by_id[v2]["purge_due_at"] is None
    assert by_id[v1]["is_accepted"] is False
    assert by_id[v1]["purge_due_at"] is not None


def test_undoing_the_acceptance_clears_the_schedule(client: TestClient) -> None:
    headers, student_id, (v1, v2) = _setup(client)
    client.post(f"/students/{student_id}/drafts/{v2}/accept", headers=headers)

    resp = client.delete(f"/students/{student_id}/drafts/{v2}/accept", headers=headers)

    assert all(d["purge_due_at"] is None for d in resp.json())
    assert not any(d["is_accepted"] for d in resp.json())


def test_a_new_upload_supersedes_the_acceptance(client: TestClient) -> None:
    headers, student_id, (_, v2) = _setup(client)
    client.post(f"/students/{student_id}/drafts/{v2}/accept", headers=headers)

    client.post(
        f"/students/{student_id}/drafts",
        files={"file": ("v3.docx", docx_bytes("Wersja 3"), _DOCX_TYPE)},
        headers=headers,
    )

    listed = client.get(f"/students/{student_id}/drafts", headers=headers).json()
    assert not any(d["is_accepted"] for d in listed)


def test_deleting_a_version_purges_it_but_keeps_it_listed(client: TestClient) -> None:
    headers, student_id, (v1, _) = _setup(client)

    resp = client.delete(f"/students/{student_id}/drafts/{v1}", headers=headers)

    assert resp.status_code == 200
    gone = next(d for d in resp.json() if d["id"] == v1)
    assert gone["purged_at"] is not None
    assert gone["has_file"] is False
    assert gone["char_count"] == len("Wersja 1")
    file_resp = client.get(f"/students/{student_id}/drafts/{v1}/file", headers=headers)
    assert file_resp.status_code == 404
    accept_resp = client.post(
        f"/students/{student_id}/drafts/{v1}/accept", headers=headers
    )
    assert accept_resp.status_code == 404


def test_graduating_a_student_records_when_supervision_ended(
    client: TestClient,
) -> None:
    headers, student_id, _ = _setup(client)

    resp = client.patch(
        f"/students/{student_id}", json={"status": "graduated"}, headers=headers
    )

    assert resp.json()["closed_at"] is not None
    listed = client.get(f"/students/{student_id}/drafts", headers=headers).json()
    assert all(d["purge_due_at"] is not None for d in listed)


async def test_actions_never_read_a_purged_version(session: AsyncSession) -> None:
    """The newest readable version is what an action gets — not an empty row."""
    students = StudentService(
        StudentRepository(session), MeetingNoteRepository(session)
    )
    repo = ThesisDraftRepository(session)
    drafts = DraftService(students, repo, SqlFileStore(session, DraftFileModel))
    student = await students.create(
        _CALLER, full_name="Jan", field_of_study="Ekonomia", thesis_type="bachelor"
    )
    first = await drafts.upload(_CALLER, student.id, "v1.docx", docx_bytes("Jeden"))
    second = await drafts.upload(_CALLER, student.id, "v2.docx", docx_bytes("Dwa"))

    await drafts.purge(_CALLER, student.id, second.draft.id)

    latest = await repo.find_latest(student.id, limit=2)
    assert [m.id for m in latest] == [first.draft.id]


async def test_newest_drafts_takes_one_version_per_student(
    session: AsyncSession,
) -> None:
    """The review list reads every thesis in one query, newest version each."""
    students = StudentService(
        StudentRepository(session), MeetingNoteRepository(session)
    )
    drafts = DraftService(
        students,
        ThesisDraftRepository(session),
        SqlFileStore(session, DraftFileModel),
    )
    jan = await students.create(
        _CALLER, full_name="Jan", field_of_study="Ekonomia", thesis_type="bachelor"
    )
    ola = await students.create(
        _CALLER, full_name="Ola", field_of_study="Ekonomia", thesis_type="bachelor"
    )
    bez = await students.create(
        _CALLER, full_name="Bez", field_of_study="Ekonomia", thesis_type="bachelor"
    )
    await drafts.upload(_CALLER, jan.id, "v1.docx", docx_bytes("Jeden"))
    jan_v2 = await drafts.upload(_CALLER, jan.id, "v2.docx", docx_bytes("Dwa"))
    ola_v1 = await drafts.upload(_CALLER, ola.id, "v1.docx", docx_bytes("Raz"))

    newest = await drafts.newest_drafts([jan, ola, bez])

    assert {k: v.draft.id for k, v in newest.items()} == {
        jan.id: jan_v2.draft.id,
        ola.id: ola_v1.draft.id,
    }
