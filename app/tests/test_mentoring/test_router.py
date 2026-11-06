"""Integration tests for the mentoring HTTP endpoints using TestClient."""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.identity.domain import user as user_domain
from src.identity.domain.user import Permission, Role
from tests.test_mentoring.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    ADMIN_UUID,
    OTHER_PROMOTOR_EMAIL,
    OTHER_PROMOTOR_PASSWORD,
    PROMOTOR_EMAIL,
    PROMOTOR_PASSWORD,
    PROMOTOR_UUID,
    login,
)

_STUDENT: dict[str, Any] = {
    "full_name": "Jan Kowalski",
    "field_of_study": "Ekonomia",
    "thesis_type": "bachelor",
}


def _create_student(
    client: TestClient,
    headers: dict[str, str],
    **overrides: Any,  # noqa: ANN401
) -> dict[str, Any]:
    payload = {**_STUDENT, **overrides}
    resp = client.post("/students", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    body: dict[str, Any] = resp.json()
    return body


# ---------- permission matrix ----------


def test_promotor_manages_own_students_only() -> None:
    promotor = user_domain.User(
        id=PROMOTOR_UUID, email=PROMOTOR_EMAIL, role=Role.PROMOTOR
    )
    assert promotor.can(Permission.MANAGE_STUDENTS) is True


def test_admin_has_no_access_to_students() -> None:
    """An admin runs the platform; theses and students are the promoters'."""
    admin = user_domain.User(id=ADMIN_UUID, email=ADMIN_EMAIL, role=Role.ADMIN)
    assert admin.can(Permission.MANAGE_STUDENTS) is False
    assert admin.can(Permission.SUBMIT_ANALYSIS) is False


# ---------- auth ----------


def test_create_student_requires_auth(client: TestClient) -> None:
    assert client.post("/students", json=_STUDENT).status_code == 401


def test_list_students_rejects_invalid_token(client: TestClient) -> None:
    resp = client.get("/students", headers={"Authorization": "Bearer nonsense"})
    assert resp.status_code == 401


def test_role_without_permission_is_forbidden(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A role that does not grant MANAGE_STUDENTS gets 403, not 401."""
    monkeypatch.setitem(
        user_domain._ROLE_PERMISSIONS,  # pyright: ignore[reportPrivateUsage]
        Role.PROMOTOR,
        frozenset({Permission.SUBMIT_ANALYSIS}),
    )
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    resp = client.get("/students", headers=headers)
    assert resp.status_code == 403


# ---------- create ----------


def test_create_student(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    body = _create_student(client, headers)

    assert body["full_name"] == "Jan Kowalski"
    assert body["promotor_id"] == str(PROMOTOR_UUID)
    assert body["status"] == "active"
    assert body["current_topic"] is None


def test_create_student_rejects_blank_name(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    resp = client.post("/students", json={**_STUDENT, "full_name": ""}, headers=headers)
    assert resp.status_code == 422


def test_create_student_rejects_unknown_thesis_type(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    resp = client.post(
        "/students", json={**_STUDENT, "thesis_type": "phd"}, headers=headers
    )
    assert resp.status_code == 422


# ---------- list ----------


def test_promotor_lists_only_own_students(client: TestClient) -> None:
    mine = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    theirs = login(client, OTHER_PROMOTOR_EMAIL, OTHER_PROMOTOR_PASSWORD)
    _create_student(client, mine, full_name="Moja Studentka")
    _create_student(client, theirs, full_name="Cudzy Student")

    resp = client.get("/students", headers=mine)
    assert resp.status_code == 200
    names = [s["full_name"] for s in resp.json()]
    assert names == ["Moja Studentka"]


def test_admin_cannot_list_or_create_students(client: TestClient) -> None:
    admin = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

    assert client.get("/students", headers=admin).status_code == 403
    assert client.post("/students", json=_STUDENT, headers=admin).status_code == 403
    assert client.get("/dashboard/summary", headers=admin).status_code == 403


def test_list_filters_by_status(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    active = _create_student(client, headers, full_name="Aktywna")
    archived = _create_student(client, headers, full_name="Zarchiwizowany")
    client.patch(
        f"/students/{archived['id']}", json={"status": "archived"}, headers=headers
    )

    resp = client.get("/students?status=active", headers=headers)
    assert [s["id"] for s in resp.json()] == [active["id"]]


# ---------- get ----------


def test_get_own_student(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    created = _create_student(client, headers)

    resp = client.get(f"/students/{created['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_other_promotors_student_is_404(client: TestClient) -> None:
    """404, not 403 — an id must not be probeable across rosters."""
    theirs = login(client, OTHER_PROMOTOR_EMAIL, OTHER_PROMOTOR_PASSWORD)
    created = _create_student(client, theirs)

    mine = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    resp = client.get(f"/students/{created['id']}", headers=mine)
    assert resp.status_code == 404


def test_admin_cannot_open_a_students_record(client: TestClient) -> None:
    theirs = login(client, OTHER_PROMOTOR_EMAIL, OTHER_PROMOTOR_PASSWORD)
    created = _create_student(client, theirs)

    admin = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    resp = client.get(f"/students/{created['id']}", headers=admin)
    assert resp.status_code == 403


def test_get_unknown_student_is_404(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    resp = client.get(f"/students/{uuid.uuid4()}", headers=headers)
    assert resp.status_code == 404


# ---------- update ----------


def test_set_topic_stamps_time(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    created = _create_student(client, headers)

    resp = client.patch(
        f"/students/{created['id']}",
        json={"current_topic": "Instytucje a wzrost gospodarczy"},
        headers=headers,
    )
    assert resp.status_code == 200
    body: dict[str, Any] = resp.json()
    assert body["current_topic"] == "Instytucje a wzrost gospodarczy"
    assert body["current_topic_set_at"] is not None


def test_update_status_only_leaves_topic_untouched(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    created = _create_student(client, headers)
    client.patch(
        f"/students/{created['id']}", json={"current_topic": "Temat"}, headers=headers
    )

    resp = client.patch(
        f"/students/{created['id']}", json={"status": "graduated"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "graduated"
    assert resp.json()["current_topic"] == "Temat"


def test_update_rejects_blank_topic(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    created = _create_student(client, headers)

    resp = client.patch(
        f"/students/{created['id']}", json={"current_topic": ""}, headers=headers
    )
    assert resp.status_code == 422


def test_update_edits_details(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    created = _create_student(client, headers)

    resp = client.patch(
        f"/students/{created['id']}",
        json={
            "full_name": "Anna Nowak",
            "field_of_study": "Finanse",
            "thesis_type": "master_article",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    body: dict[str, Any] = resp.json()
    assert body["full_name"] == "Anna Nowak"
    assert body["field_of_study"] == "Finanse"
    assert body["thesis_type"] == "master_article"
    assert "index_number" not in body


def test_null_clears_topic(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    created = _create_student(client, headers)
    url = f"/students/{created['id']}"
    client.patch(url, json={"current_topic": "Temat"}, headers=headers)

    kept = client.patch(url, json={"full_name": "Anna Nowak"}, headers=headers)
    cleared = client.patch(url, json={"current_topic": None}, headers=headers)

    assert kept.json()["current_topic"] == "Temat"
    assert cleared.json()["current_topic"] is None
    assert cleared.json()["current_topic_set_at"] is None


def test_an_index_number_from_an_old_client_is_ignored(client: TestClient) -> None:
    """Corvus does not keep it; a tab opened before the change still works."""
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)

    resp = client.post(
        "/students", json={**_STUDENT, "index_number": "123456"}, headers=headers
    )

    assert resp.status_code == 201, resp.text
    assert "index_number" not in resp.json()


def test_update_rejects_blank_name(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    created = _create_student(client, headers)

    resp = client.patch(
        f"/students/{created['id']}", json={"full_name": ""}, headers=headers
    )
    assert resp.status_code == 422


def test_update_other_promotors_student_is_404(client: TestClient) -> None:
    theirs = login(client, OTHER_PROMOTOR_EMAIL, OTHER_PROMOTOR_PASSWORD)
    created = _create_student(client, theirs)

    mine = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    resp = client.patch(
        f"/students/{created['id']}", json={"status": "archived"}, headers=mine
    )
    assert resp.status_code == 404


# ---------- meeting notes ----------


def test_create_and_list_meeting_notes(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    created = _create_student(client, headers)

    first = client.post(
        f"/students/{created['id']}/meeting-notes",
        json={"content": "Ustaliliśmy zakres", "occurred_at": "2026-03-01T10:00:00Z"},
        headers=headers,
    )
    assert first.status_code == 201, first.text
    assert first.json()["promotor_id"] == str(PROMOTOR_UUID)
    assert first.json()["source_action_id"] is None

    client.post(
        f"/students/{created['id']}/meeting-notes",
        json={
            "content": "Omówiliśmy metodologię",
            "occurred_at": "2026-04-01T10:00:00Z",
        },
        headers=headers,
    )

    resp = client.get(f"/students/{created['id']}/meeting-notes", headers=headers)
    assert resp.status_code == 200
    assert [n["content"] for n in resp.json()] == [
        "Omówiliśmy metodologię",
        "Ustaliliśmy zakres",
    ]


def test_meeting_note_defaults_occurred_at_to_now(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    created = _create_student(client, headers)

    resp = client.post(
        f"/students/{created['id']}/meeting-notes",
        json={"content": "Spotkanie ad hoc"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["occurred_at"] is not None


def test_meeting_note_rejects_blank_content(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    created = _create_student(client, headers)

    resp = client.post(
        f"/students/{created['id']}/meeting-notes",
        json={"content": "   "},
        headers=headers,
    )
    assert resp.status_code == 422


def test_meeting_note_on_other_promotors_student_is_404(client: TestClient) -> None:
    theirs = login(client, OTHER_PROMOTOR_EMAIL, OTHER_PROMOTOR_PASSWORD)
    created = _create_student(client, theirs)

    mine = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    resp = client.post(
        f"/students/{created['id']}/meeting-notes",
        json={"content": "Nie moja notatka"},
        headers=mine,
    )
    assert resp.status_code == 404


def test_listing_notes_of_other_promotors_student_is_404(client: TestClient) -> None:
    theirs = login(client, OTHER_PROMOTOR_EMAIL, OTHER_PROMOTOR_PASSWORD)
    created = _create_student(client, theirs)

    mine = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    resp = client.get(f"/students/{created['id']}/meeting-notes", headers=mine)
    assert resp.status_code == 404


def test_research_area_and_aim_are_kept_and_cleared(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    created = client.post(
        "/students",
        json={
            "full_name": "Jan Kowalski",
            "field_of_study": "Ekonomia",
            "thesis_type": "bachelor",
            "research_area": "ekonomia instytucjonalna",
            "research_aim": "Cel: zbadać X.",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["research_area"] == "ekonomia instytucjonalna"
    assert body["research_aim"] == "Cel: zbadać X."

    # Left out: kept. Sent as null: cleared.
    student_id = body["id"]
    renamed = client.patch(
        f"/students/{student_id}", json={"full_name": "Jan K."}, headers=headers
    )
    assert renamed.json()["research_aim"] == "Cel: zbadać X."

    cleared = client.patch(
        f"/students/{student_id}", json={"research_aim": None}, headers=headers
    )
    assert cleared.json()["research_aim"] is None
    assert cleared.json()["research_area"] == "ekonomia instytucjonalna"
