"""Integration tests for parts of a thesis and the fragments handed in."""

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient

from src.mentoring.application.fragment_service import MAX_PASTED_CHARS
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


def _paste(
    client: TestClient,
    headers: dict[str, str],
    student_id: str,
    part_name: str = "Rozdział 1",
    text: str = "Przegląd literatury o bezrobociu.",
    **fields: str,
) -> Any:  # noqa: ANN401
    return client.post(
        f"/students/{student_id}/fragments",
        data={"part_name": part_name, "text": text, **fields},
        headers=headers,
    )


def test_pasted_text_is_round_one_of_a_new_part(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)

    resp = _paste(client, headers, student_id, question="Czy to dobry kierunek?")

    assert resp.status_code == 201, resp.text
    body: dict[str, Any] = resp.json()
    assert body["round_number"] == 1
    assert body["format"] == "text"
    assert body["question"] == "Czy to dobry kierunek?"
    assert body["has_file"] is False
    assert body["verdict"] is None
    assert "text" not in body


def test_a_file_can_be_downloaded_again(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    data = docx_bytes("Rozdział drugi: metodologia badania.")

    resp = client.post(
        f"/students/{student_id}/fragments",
        data={"part_name": "Rozdział 2"},
        files={"file": ("rozdz2.docx", data, _DOCX_TYPE)},
        headers=headers,
    )

    assert resp.status_code == 201, resp.text
    body: dict[str, Any] = resp.json()
    assert body["format"] == "docx"
    assert body["filename"] == "rozdz2.docx"
    assert "metodologia" in body["preview"]
    download = client.get(
        f"/students/{student_id}/fragments/{body['id']}/file", headers=headers
    )
    assert download.status_code == 200
    assert download.content == data


def test_pasted_text_has_no_file_to_download(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    fragment_id = _paste(client, headers, student_id).json()["id"]

    resp = client.get(
        f"/students/{student_id}/fragments/{fragment_id}/file", headers=headers
    )

    assert resp.status_code == 404


def test_the_same_part_gets_the_next_round_whatever_the_case(
    client: TestClient,
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)

    first = _paste(client, headers, student_id, part_name="Rozdział 1").json()
    second = _paste(client, headers, student_id, part_name=" rozdział 1 ").json()
    other = _paste(client, headers, student_id, part_name="Rozdział 2").json()

    assert second["part_id"] == first["part_id"]
    assert second["round_number"] == 2
    assert other["round_number"] == 1


def test_a_fragment_needs_exactly_one_source(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)

    neither = client.post(
        f"/students/{student_id}/fragments",
        data={"part_name": "Rozdział 1"},
        headers=headers,
    )
    both = client.post(
        f"/students/{student_id}/fragments",
        data={"part_name": "Rozdział 1", "text": "Tekst."},
        files={"file": ("r.docx", docx_bytes("Tekst."), _DOCX_TYPE)},
        headers=headers,
    )

    assert neither.status_code == 422
    assert both.status_code == 422


def test_blank_or_oversized_text_is_refused(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)

    blank = _paste(client, headers, student_id, text="   ")
    oversized = _paste(client, headers, student_id, text="x" * (MAX_PASTED_CHARS + 1))

    assert blank.status_code == 422
    assert oversized.status_code == 422


def test_an_unreadable_file_is_refused(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)

    resp = client.post(
        f"/students/{student_id}/fragments",
        data={"part_name": "Rozdział 1"},
        files={"file": ("r.docx", b"not a document", _DOCX_TYPE)},
        headers=headers,
    )

    assert resp.status_code == 422


def test_received_on_can_be_past_but_not_future(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    today = datetime.now(UTC).date()

    past = _paste(
        client,
        headers,
        student_id,
        received_on=(today - timedelta(days=7)).isoformat(),
    )
    future = _paste(
        client,
        headers,
        student_id,
        received_on=(today + timedelta(days=5)).isoformat(),
    )

    assert past.json()["received_on"] == (today - timedelta(days=7)).isoformat()
    assert future.status_code == 422


def test_a_fragment_does_not_become_the_thesis(client: TestClient) -> None:
    """The reason fragments are their own table: versions never see them."""
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)

    _paste(client, headers, student_id)

    drafts = client.get(f"/students/{student_id}/drafts", headers=headers)
    assert drafts.json() == []


def test_a_part_can_be_planned_with_a_deadline(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)

    resp = client.post(
        f"/students/{student_id}/parts",
        json={"name": "Rozdział 3", "due_on": "2026-11-30"},
        headers=headers,
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["due_on"] == "2026-11-30"
    assert resp.json()["position"] == 1


def test_a_fragment_clears_the_deadline_of_its_part(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    part = client.post(
        f"/students/{student_id}/parts",
        json={"name": "Rozdział 3", "due_on": "2026-11-30"},
        headers=headers,
    ).json()

    _paste(client, headers, student_id, part_name="Rozdział 3")

    # Renaming it answers with every part, which is all this needs to read.
    parts = client.patch(
        f"/students/{student_id}/parts/{part['id']}",
        json={"name": "Rozdział 3: wyniki"},
        headers=headers,
    ).json()
    assert parts[0]["due_on"] is None


def test_part_names_are_unique_per_student(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    url = f"/students/{student_id}/parts"
    client.post(url, json={"name": "Wstęp"}, headers=headers)
    other = client.post(url, json={"name": "Rozdział 1"}, headers=headers).json()

    duplicate = client.post(url, json={"name": "WSTĘP"}, headers=headers)
    renamed = client.patch(
        f"{url}/{other['id']}", json={"name": "wstęp"}, headers=headers
    )

    assert duplicate.status_code == 409
    assert renamed.status_code == 409


def test_a_part_can_be_moved_and_its_deadline_cleared(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    url = f"/students/{student_id}/parts"
    client.post(url, json={"name": "Rozdział 1"}, headers=headers)
    client.post(url, json={"name": "Rozdział 2"}, headers=headers)
    intro = client.post(
        url, json={"name": "Wstęp", "due_on": "2026-11-30"}, headers=headers
    ).json()

    moved = client.patch(
        f"{url}/{intro['id']}", json={"position": 1}, headers=headers
    ).json()

    assert [p["name"] for p in moved] == ["Wstęp", "Rozdział 1", "Rozdział 2"]
    assert [p["position"] for p in moved] == [1, 2, 3]
    assert moved[0]["due_on"] == "2026-11-30"

    cleared = client.patch(
        f"{url}/{intro['id']}", json={"due_on": None}, headers=headers
    ).json()
    assert cleared[0]["due_on"] is None


def test_only_an_empty_part_can_be_deleted(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    url = f"/students/{student_id}/parts"
    empty = client.post(url, json={"name": "Rozdział 3"}, headers=headers).json()
    used = _paste(client, headers, student_id, part_name="Rozdział 1").json()

    assert (
        client.delete(f"{url}/{empty['id']}", headers=headers).status_code == 204
    )
    assert (
        client.delete(f"{url}/{used['part_id']}", headers=headers).status_code == 409
    )


def test_another_promoter_sees_none_of_it(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    other = login(client, OTHER_PROMOTOR_EMAIL, OTHER_PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    fragment = _paste(client, headers, student_id).json()

    assert _paste(client, other, student_id).status_code == 404
    assert (
        client.get(
            f"/students/{student_id}/fragments/{fragment['id']}/file", headers=other
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/students/{student_id}/parts", json={"name": "X"}, headers=other
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/students/{student_id}/parts/{fragment['part_id']}", headers=other
        ).status_code
        == 404
    )
