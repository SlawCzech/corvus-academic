"""Integration tests for uploading thesis versions."""

import hashlib
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.shared.settings import settings
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

_DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


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


def test_upload_keeps_the_original_file(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    original = docx_bytes("Rozdział 1: Wprowadzenie.")

    body: dict[str, Any] = client.post(
        f"/students/{student_id}/drafts",
        files={"file": ("Praca końcowa.docx", original, _DOCX_TYPE)},
        headers=headers,
    ).json()

    assert body["has_file"] is True
    assert body["file_size"] == len(original)
    assert body["file_sha256"] == hashlib.sha256(original).hexdigest()


def test_download_returns_the_same_bytes_as_an_attachment(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    original = docx_bytes("Rozdział 1: Wprowadzenie.")
    draft_id = client.post(
        f"/students/{student_id}/drafts",
        files={"file": ("Praca końcowa.docx", original, _DOCX_TYPE)},
        headers=headers,
    ).json()["id"]

    resp = client.get(f"/students/{student_id}/drafts/{draft_id}/file", headers=headers)

    assert resp.status_code == 200
    assert resp.content == original
    assert resp.headers["content-type"] == _DOCX_TYPE
    disposition = resp.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    # Non-ASCII filenames survive the header, percent-encoded.
    assert "Praca%20ko%C5%84cowa.docx" in disposition


def test_download_of_another_promotors_draft_is_404(client: TestClient) -> None:
    theirs = login(client, OTHER_PROMOTOR_EMAIL, OTHER_PROMOTOR_PASSWORD)
    student_id = _new_student(client, theirs)
    draft_id = _upload(client, theirs, student_id).json()["id"]

    mine = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    resp = client.get(f"/students/{student_id}/drafts/{draft_id}/file", headers=mine)

    assert resp.status_code == 404


def test_download_of_a_draft_from_another_student_is_404(client: TestClient) -> None:
    """A valid draft id under the wrong student must not leak the file."""
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    first = _new_student(client, headers)
    second = _new_student(client, headers)
    draft_id = _upload(client, headers, first).json()["id"]

    resp = client.get(f"/students/{second}/drafts/{draft_id}/file", headers=headers)

    assert resp.status_code == 404


def test_oversized_upload_is_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "max_upload_bytes", 1024)
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)

    resp = client.post(
        f"/students/{student_id}/drafts",
        files={"file": ("praca.docx", b"PK\x03\x04" + b"x" * 2048, _DOCX_TYPE)},
        headers=headers,
    )

    assert resp.status_code == 413


def test_file_whose_content_contradicts_its_name_is_rejected(
    client: TestClient,
) -> None:
    """A DOCX renamed to .pdf is refused rather than stored under a lie."""
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)

    resp = client.post(
        f"/students/{student_id}/drafts",
        files={"file": ("praca.pdf", docx_bytes(), "application/pdf")},
        headers=headers,
    )

    assert resp.status_code == 422
    assert "not a valid PDF" in resp.json()["detail"]
