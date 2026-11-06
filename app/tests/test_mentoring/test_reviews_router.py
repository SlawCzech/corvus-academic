"""One-off reviews: a thesis with nobody to supervise (ADR 0017)."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from src.mentoring.application.retention_service import RetentionService
from src.mentoring.domain.student import Student, StudentStatus, ThesisType
from src.mentoring.infrastructure.dependencies import get_agent_client
from src.mentoring.infrastructure.orm import DraftFileModel, StudentModel
from src.mentoring.infrastructure.repositories import (
    StudentRepository,
    ThesisDraftRepository,
    ThesisFragmentRepository,
)
from src.shared.sql_file_store import SqlFileStore
from tests.test_mentoring.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    OTHER_PROMOTOR_EMAIL,
    OTHER_PROMOTOR_PASSWORD,
    PROMOTOR_EMAIL,
    PROMOTOR_PASSWORD,
    guideline_set,
    login,
)
from tests.test_mentoring.fakes import FakeAgentClient, docx_bytes

_DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_FIELDS: dict[str, str] = {
    "full_name": "Anna Nowak",
    "field_of_study": "Ekonomia",
    "thesis_type": "master_article",
}


@pytest.fixture
def agent() -> Generator[FakeAgentClient, None, None]:
    fake = FakeAgentClient()
    app.dependency_overrides[get_agent_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_agent_client, None)


@pytest.fixture
def headers(client: TestClient) -> dict[str, str]:
    return login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)


def _create(
    client: TestClient,
    headers: dict[str, str],
    **fields: str,
) -> Any:  # noqa: ANN401
    return client.post(
        "/reviews",
        data={
            **_FIELDS,
            "guideline_set_id": guideline_set(
                client, fields.get("thesis_type", _FIELDS["thesis_type"])
            ),
            **fields,
        },
        files={"file": ("praca.docx", docx_bytes("Rozdział 1: Wstęp."), _DOCX_TYPE)},
        headers=headers,
    )


def _new_review(client: TestClient, headers: dict[str, str]) -> str:
    resp = _create(client, headers)
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


# ---------- domain ----------


def _one_off() -> Student:
    return Student.one_off(
        id=uuid.uuid4(),
        promotor_id=uuid.uuid4(),
        full_name="Anna Nowak",
        field_of_study="Ekonomia",
        thesis_type=ThesisType.BACHELOR,
    )


def test_a_one_off_is_born_archived_with_its_clock_running() -> None:
    student = _one_off()

    assert student.is_one_off
    assert student.status is StudentStatus.ARCHIVED
    assert student.closed_at == student.created_at


def test_promotion_stops_the_clock_and_makes_a_student() -> None:
    student = _one_off()

    student.promote()

    assert not student.is_one_off
    assert student.status is StudentStatus.ACTIVE
    assert student.closed_at is None


def test_a_one_off_has_no_lifecycle_status() -> None:
    with pytest.raises(ValueError, match="no lifecycle"):
        _one_off().change_status(StudentStatus.ACTIVE)


def test_only_a_one_off_can_be_promoted() -> None:
    student = _one_off()
    student.promote()

    with pytest.raises(ValueError, match="Only a one-off"):
        student.promote()


# ---------- making one ----------


def test_create_stores_the_review_and_its_thesis(
    client: TestClient, headers: dict[str, str]
) -> None:
    resp = _create(client, headers, current_topic="Handel a instytucje")

    assert resp.status_code == 201, resp.text
    body: dict[str, Any] = resp.json()
    assert body["full_name"] == "Anna Nowak"
    assert body["current_topic"] == "Handel a instytucje"
    assert body["filename"] == "praca.docx"
    assert body["purge_due_at"] is not None

    drafts = client.get(f"/students/{body['id']}/drafts", headers=headers).json()
    assert [d["version_number"] for d in drafts] == [1]


async def test_a_file_nobody_can_read_leaves_nothing_behind(
    client: TestClient, headers: dict[str, str], db_session: AsyncSession
) -> None:
    resp = client.post(
        "/reviews",
        data=_FIELDS,
        files={"file": ("praca.txt", b"nie praca", "text/plain")},
        headers=headers,
    )

    assert resp.status_code == 422
    assert client.get("/reviews", headers=headers).json() == []
    count = await db_session.scalar(select(func.count()).select_from(StudentModel))
    assert count == 0


def test_a_blank_author_is_refused(client: TestClient, headers: dict[str, str]) -> None:
    assert _create(client, headers, full_name="   ").status_code == 422
    assert client.get("/reviews", headers=headers).json() == []


# ---------- the title page ----------


def test_the_title_page_suggests_and_nothing_is_stored(
    client: TestClient, headers: dict[str, str]
) -> None:
    thesis = docx_bytes("KIERUNEK EKONOMIA", "Anna Nowak", "123456", "Praca o handlu")

    resp = client.post(
        "/reviews/title-page",
        files={"file": ("praca.docx", thesis, _DOCX_TYPE)},
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "full_name": "Anna Nowak",
        "field_of_study": "Ekonomia",
        "thesis_type": None,
        "current_topic": "Praca o handlu",
    }
    assert client.get("/reviews", headers=headers).json() == []


def test_a_file_nobody_can_read_suggests_nothing(
    client: TestClient, headers: dict[str, str]
) -> None:
    resp = client.post(
        "/reviews/title-page",
        files={"file": ("praca.txt", b"nie praca", "text/plain")},
        headers=headers,
    )

    assert resp.status_code == 422


def test_the_title_page_is_not_for_the_admin(client: TestClient) -> None:
    admin = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

    resp = client.post(
        "/reviews/title-page",
        files={"file": ("praca.docx", docx_bytes("Tekst."), _DOCX_TYPE)},
        headers=admin,
    )

    assert resp.status_code == 403


# ---------- where it shows ----------


def test_the_history_lists_reviews_and_the_roster_does_not(
    client: TestClient, headers: dict[str, str]
) -> None:
    review_id = _new_review(client, headers)

    history = client.get("/reviews", headers=headers).json()
    assert [r["id"] for r in history] == [review_id]
    assert client.get("/students", headers=headers).json() == []
    archived = client.get("/students?status=archived", headers=headers).json()
    assert archived == []


def test_it_stays_out_of_the_dashboard_counters(
    client: TestClient, headers: dict[str, str], agent: FakeAgentClient
) -> None:
    _new_review(client, headers)

    summary = client.get("/dashboard/summary", headers=headers).json()

    assert summary["active_students"] == 0
    assert summary["without_topic"] == 0


def test_an_unfinished_action_is_named_after_the_author(
    client: TestClient, headers: dict[str, str], agent: FakeAgentClient
) -> None:
    review_id = _new_review(client, headers)
    agent.runs_with({"steps": ["a"], "done": []})
    client.post(
        f"/students/{review_id}/actions",
        json={"provider": "claude", "action_type": "generate_review"},
        headers=headers,
    )

    listed = client.get("/dashboard/actions-in-progress", headers=headers).json()

    assert [a["student_name"] for a in listed] == ["Anna Nowak"]


def test_a_review_belongs_to_whoever_made_it(
    client: TestClient, headers: dict[str, str]
) -> None:
    review_id = _new_review(client, headers)
    other = login(client, OTHER_PROMOTOR_EMAIL, OTHER_PROMOTOR_PASSWORD)

    assert client.get("/reviews", headers=other).json() == []
    resp = client.post(f"/reviews/{review_id}/promote", headers=other)
    assert resp.status_code == 404


def test_the_admin_has_no_way_in(client: TestClient) -> None:
    admin = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

    assert client.get("/reviews", headers=admin).status_code == 403


# ---------- what it takes ----------


@pytest.mark.parametrize(
    "action_type", ["generate_review", "verify_bibliography", "defence_questions"]
)
def test_a_reviewers_actions_run(
    client: TestClient,
    headers: dict[str, str],
    agent: FakeAgentClient,
    action_type: str,
) -> None:
    review_id = _new_review(client, headers)

    resp = client.post(
        f"/students/{review_id}/actions",
        json={"provider": "claude", "action_type": action_type},
        headers=headers,
    )

    assert resp.status_code == 202, resp.text


def test_the_review_is_told_how_to_refer_to_the_author(
    client: TestClient, headers: dict[str, str], agent: FakeAgentClient
) -> None:
    review_id = _new_review(client, headers)

    client.post(
        f"/students/{review_id}/actions",
        json={"provider": "claude", "action_type": "generate_review"},
        headers=headers,
    )

    assert agent.submitted[0]["context"]["metadata"]["author_form"] == "Autorka"


@pytest.mark.parametrize(
    "action_type",
    ["propose_topic", "check_progress", "draft_meeting_note", "trial_review"],
)
def test_the_supervising_actions_are_refused(
    client: TestClient,
    headers: dict[str, str],
    agent: FakeAgentClient,
    action_type: str,
) -> None:
    review_id = _new_review(client, headers)

    resp = client.post(
        f"/students/{review_id}/actions",
        json={"provider": "claude", "action_type": action_type, "detail": "punkty"},
        headers=headers,
    )

    assert resp.status_code == 409
    assert agent.submitted == []


def test_a_note_is_refused(client: TestClient, headers: dict[str, str]) -> None:
    review_id = _new_review(client, headers)

    resp = client.post(
        f"/students/{review_id}/meeting-notes",
        json={"content": "Spotkanie"},
        headers=headers,
    )

    assert resp.status_code == 409


def test_a_second_version_is_refused(
    client: TestClient, headers: dict[str, str]
) -> None:
    review_id = _new_review(client, headers)

    resp = client.post(
        f"/students/{review_id}/drafts",
        files={"file": ("v2.docx", docx_bytes("Druga wersja."), _DOCX_TYPE)},
        headers=headers,
    )

    assert resp.status_code == 409


def test_parts_and_fragments_are_refused(
    client: TestClient, headers: dict[str, str]
) -> None:
    review_id = _new_review(client, headers)

    part = client.post(
        f"/students/{review_id}/parts", json={"name": "Rozdział 1"}, headers=headers
    )
    fragment = client.post(
        f"/students/{review_id}/fragments",
        data={"part_name": "Rozdział 1", "text": "Tekst."},
        headers=headers,
    )

    assert part.status_code == 409
    assert fragment.status_code == 409


def test_patching_the_status_is_refused_and_changes_nothing(
    client: TestClient, headers: dict[str, str]
) -> None:
    review_id = _new_review(client, headers)

    resp = client.patch(
        f"/students/{review_id}",
        json={"status": "active", "field_of_study": "Finanse"},
        headers=headers,
    )

    assert resp.status_code == 422
    student = client.get(f"/students/{review_id}", headers=headers).json()
    assert student["status"] == "archived"
    assert student["closed_at"] is not None


def test_details_and_guidelines_can_still_be_edited(
    client: TestClient, headers: dict[str, str]
) -> None:
    review_id = _new_review(client, headers)

    resp = client.patch(
        f"/students/{review_id}", json={"field_of_study": "Finanse"}, headers=headers
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["field_of_study"] == "Finanse"
    assert resp.json()["is_one_off"] is True


# ---------- promotion ----------


def test_promotion_puts_the_author_on_the_roster(
    client: TestClient, headers: dict[str, str], agent: FakeAgentClient
) -> None:
    review_id = _new_review(client, headers)
    client.post(
        f"/students/{review_id}/actions",
        json={"provider": "claude", "action_type": "generate_review"},
        headers=headers,
    )

    resp = client.post(f"/reviews/{review_id}/promote", headers=headers)

    assert resp.status_code == 200, resp.text
    assert resp.json()["is_one_off"] is False
    assert resp.json()["status"] == "active"
    assert resp.json()["closed_at"] is None
    assert client.get("/reviews", headers=headers).json() == []
    assert [s["id"] for s in client.get("/students", headers=headers).json()] == [
        review_id
    ]
    actions = client.get(f"/students/{review_id}/actions", headers=headers).json()
    assert len(actions) == 1
    drafts = client.get(f"/students/{review_id}/drafts", headers=headers).json()
    assert drafts[0]["purge_due_at"] is None


def test_promoting_twice_is_a_conflict(
    client: TestClient, headers: dict[str, str]
) -> None:
    review_id = _new_review(client, headers)

    client.post(f"/reviews/{review_id}/promote", headers=headers)
    resp = client.post(f"/reviews/{review_id}/promote", headers=headers)

    assert resp.status_code == 409


def test_a_promoted_review_takes_notes_and_versions(
    client: TestClient, headers: dict[str, str]
) -> None:
    review_id = _new_review(client, headers)
    client.post(f"/reviews/{review_id}/promote", headers=headers)

    note = client.post(
        f"/students/{review_id}/meeting-notes",
        json={"content": "Spotkanie"},
        headers=headers,
    )
    version = client.post(
        f"/students/{review_id}/drafts",
        files={"file": ("v2.docx", docx_bytes("Druga wersja."), _DOCX_TYPE)},
        headers=headers,
    )

    assert note.status_code == 201
    assert version.json()["version_number"] == 2


# ---------- retention and delete ----------


async def test_retention_empties_it_after_30_days_and_keeps_it_listed(
    client: TestClient, headers: dict[str, str], db_session: AsyncSession
) -> None:
    review_id = _new_review(client, headers)
    sweep = RetentionService(
        StudentRepository(db_session),
        ThesisDraftRepository(db_session),
        ThesisFragmentRepository(db_session),
        SqlFileStore(db_session, DraftFileModel),
    )

    now = datetime.now(UTC)
    assert await sweep.sweep(now + timedelta(days=29)) == 0
    assert await sweep.sweep(now + timedelta(days=31)) == 1

    listed = client.get("/reviews", headers=headers).json()
    assert [r["id"] for r in listed] == [review_id]
    assert listed[0]["purged_at"] is not None


def test_delete_is_the_ordinary_one(
    client: TestClient, headers: dict[str, str], agent: FakeAgentClient
) -> None:
    review_id = _new_review(client, headers)

    assert client.delete(f"/students/{review_id}", headers=headers).status_code == 204
    assert client.get("/reviews", headers=headers).json() == []
