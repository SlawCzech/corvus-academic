"""Integration tests for uploading thesis versions."""

from typing import Any

from fastapi.testclient import TestClient

from tests.test_mentoring.conftest import (
    OTHER_PROMOTOR_EMAIL,
    OTHER_PROMOTOR_PASSWORD,
    PROMOTOR_EMAIL,
    PROMOTOR_PASSWORD,
    login,
)
from tests.test_mentoring.fakes import docx_bytes

_STUDENT: dict[str, Any] = {
    "full_name": "Jan Kowalski",
    "field_of_study": "Ekonomia",
    "thesis_type": "bachelor",
}

_DOCX_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


def _new_student(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post("/students", json=_STUDENT, headers=headers)
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


def _upload(
    client: TestClient,
    headers: dict[str, str],
    student_id: str,
    filename: str = "praca.docx",
    text: str = "Rozdział 1: Wprowadzenie.",
) -> Any:  # noqa: ANN401
    return client.post(
        f"/students/{student_id}/drafts",
        files={"file": (filename, docx_bytes(text), _DOCX_TYPE)},
        headers=headers,
    )


def test_upload_stores_the_first_version(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)

    resp = _upload(client, headers, student_id)

    assert resp.status_code == 201, resp.text
    body: dict[str, Any] = resp.json()
    assert body["version_number"] == 1
    assert body["format"] == "docx"
    assert body["char_count"] > 0
    assert "Rozdział 1" in body["preview"]
    # The extracted text is stored, not echoed — a thesis is megabytes.
    assert "text" not in body


def test_versions_are_numbered_per_student(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    first_student = _new_student(client, headers)
    second_student = _new_student(client, headers)

    _upload(client, headers, first_student)
    second = _upload(client, headers, first_student)
    other_first = _upload(client, headers, second_student)

    assert second.json()["version_number"] == 2
    assert other_first.json()["version_number"] == 1


def test_list_returns_newest_version_first(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    _upload(client, headers, student_id, text="Wersja pierwsza")
    _upload(client, headers, student_id, text="Wersja druga")

    resp = client.get(f"/students/{student_id}/drafts", headers=headers)

    assert resp.status_code == 200
    versions = [d["version_number"] for d in resp.json()]
    assert versions == [2, 1]


def test_unsupported_file_type_is_rejected(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)

    resp = client.post(
        f"/students/{student_id}/drafts",
        files={"file": ("notatki.txt", b"zwykly tekst", "text/plain")},
        headers=headers,
    )

    assert resp.status_code == 422


def test_unreadable_file_is_rejected(client: TestClient) -> None:
    """A .docx that is not a docx must not become an empty draft."""
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)

    resp = client.post(
        f"/students/{student_id}/drafts",
        files={"file": ("praca.docx", b"not really a docx", _DOCX_TYPE)},
        headers=headers,
    )

    assert resp.status_code == 422


def test_upload_to_another_promotors_student_is_404(client: TestClient) -> None:
    theirs = login(client, OTHER_PROMOTOR_EMAIL, OTHER_PROMOTOR_PASSWORD)
    student_id = _new_student(client, theirs)

    mine = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    assert _upload(client, mine, student_id).status_code == 404


def test_upload_requires_auth(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)

    resp = client.post(
        f"/students/{student_id}/drafts",
        files={"file": ("praca.docx", docx_bytes(), _DOCX_TYPE)},
    )
    assert resp.status_code == 401
