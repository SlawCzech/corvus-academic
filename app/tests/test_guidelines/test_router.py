"""Integration tests for the guideline catalog API."""

import hashlib
from typing import Any

from fastapi.testclient import TestClient

from tests.test_mentoring.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    PROMOTOR_EMAIL,
    PROMOTOR_PASSWORD,
    login,
)
from tests.test_mentoring.fakes import docx_bytes

_DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _admin(client: TestClient) -> dict[str, str]:
    return login(client, ADMIN_EMAIL, ADMIN_PASSWORD)


def _promotor(client: TestClient) -> dict[str, str]:
    return login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)


def _set(client: TestClient, admin: dict[str, str]) -> dict[str, Any]:
    university = client.post(
        "/guidelines/admin/universities",
        json={
            "name": "Uniwersytet Ekonomiczny w Katowicach",
            "short_name": "UE Katowice",
        },
        headers=admin,
    ).json()
    resp = client.post(
        "/guidelines/admin/sets",
        json={
            "university_id": university["id"],
            "thesis_type": "bachelor",
            "name": "Prace licencjackie",
        },
        headers=admin,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _published(
    client: TestClient, admin: dict[str, str], set_id: str, rubric: str
) -> dict[str, Any]:
    draft = client.post(
        f"/guidelines/admin/sets/{set_id}/versions",
        json={"rubric_md": rubric, "thresholds": {"min_sources": 25}},
        headers=admin,
    ).json()
    resp = client.post(
        f"/guidelines/admin/versions/{draft['id']}/publish", headers=admin
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_admin_publishes_and_the_previous_version_is_superseded(
    client: TestClient,
) -> None:
    admin = _admin(client)
    guideline_set = _set(client, admin)
    first = _published(client, admin, guideline_set["id"], "## v1")

    second = _published(client, admin, guideline_set["id"], "## v2")

    assert second["version_no"] == 2 and second["status"] == "published"
    history = client.get(f"/guidelines/sets/{guideline_set['id']}", headers=admin)
    statuses = {v["id"]: v["status"] for v in history.json()["versions"]}
    assert statuses == {second["id"]: "published", first["id"]: "superseded"}


def test_a_new_draft_starts_from_the_version_in_force(client: TestClient) -> None:
    admin = _admin(client)
    guideline_set = _set(client, admin)
    _published(client, admin, guideline_set["id"], "## Wymogi v1")

    draft = client.post(
        f"/guidelines/admin/sets/{guideline_set['id']}/versions", json={}, headers=admin
    ).json()

    assert draft["status"] == "draft"
    assert draft["rubric_md"] == "## Wymogi v1"
    assert draft["thresholds"]["min_sources"] == 25


def test_a_second_draft_of_the_same_set_is_a_conflict(client: TestClient) -> None:
    admin = _admin(client)
    guideline_set = _set(client, admin)
    url = f"/guidelines/admin/sets/{guideline_set['id']}/versions"
    client.post(url, json={"rubric_md": "a"}, headers=admin)

    assert client.post(url, json={"rubric_md": "b"}, headers=admin).status_code == 409


def test_a_published_version_cannot_be_edited(client: TestClient) -> None:
    admin = _admin(client)
    guideline_set = _set(client, admin)
    published = _published(client, admin, guideline_set["id"], "## v1")

    resp = client.patch(
        f"/guidelines/admin/versions/{published['id']}",
        json={"rubric_md": "rewritten history"},
        headers=admin,
    )

    assert resp.status_code == 409


def test_promotor_reads_the_catalog_but_never_a_draft(client: TestClient) -> None:
    admin = _admin(client)
    guideline_set = _set(client, admin)
    published = _published(client, admin, guideline_set["id"], "## v1")
    draft = client.post(
        f"/guidelines/admin/sets/{guideline_set['id']}/versions", json={}, headers=admin
    ).json()
    promotor = _promotor(client)

    sets = client.get("/guidelines/sets?thesis_type=bachelor", headers=promotor).json()
    assert [s["current"]["id"] for s in sets] == [published["id"]]
    assert sets[0]["has_draft"] is False
    assert sets[0]["university"]["short_name"] == "UE Katowice"
    detail = client.get(f"/guidelines/versions/{published['id']}", headers=promotor)
    assert detail.json()["rubric_md"] == "## v1"
    assert (
        client.get(f"/guidelines/versions/{draft['id']}", headers=promotor).status_code
        == 404
    )


def test_a_set_with_only_a_draft_is_invisible_to_promotors(client: TestClient) -> None:
    admin = _admin(client)
    guideline_set = _set(client, admin)
    client.post(
        f"/guidelines/admin/sets/{guideline_set['id']}/versions",
        json={"rubric_md": "work in progress"},
        headers=admin,
    )
    promotor = _promotor(client)

    assert client.get("/guidelines/sets", headers=promotor).json() == []
    admin_view = client.get("/guidelines/sets", headers=admin).json()
    assert admin_view[0]["has_draft"] is True


def test_promotor_cannot_write(client: TestClient) -> None:
    promotor = _promotor(client)

    resp = client.post(
        "/guidelines/admin/universities",
        json={"name": "Inna", "short_name": "Inna"},
        headers=promotor,
    )

    assert resp.status_code == 403


def test_the_original_regulation_is_stored_and_downloadable(
    client: TestClient,
) -> None:
    admin = _admin(client)
    guideline_set = _set(client, admin)
    draft = client.post(
        f"/guidelines/admin/sets/{guideline_set['id']}/versions",
        json={"rubric_md": "## v1"},
        headers=admin,
    ).json()
    original = docx_bytes("Zarządzenie nr 117/22")

    attached = client.put(
        f"/guidelines/admin/versions/{draft['id']}/source",
        files={"file": ("Zarządzenie 117-22.docx", original, _DOCX_TYPE)},
        headers=admin,
    )
    client.post(f"/guidelines/admin/versions/{draft['id']}/publish", headers=admin)

    assert attached.status_code == 200, attached.text
    source = attached.json()["source"]
    assert source["sha256"] == hashlib.sha256(original).hexdigest()
    download = client.get(
        f"/guidelines/versions/{draft['id']}/source", headers=_promotor(client)
    )
    assert download.status_code == 200
    assert download.content == original
    assert download.headers["content-disposition"].startswith("attachment;")


def test_a_source_that_is_not_pdf_or_docx_is_rejected(client: TestClient) -> None:
    admin = _admin(client)
    guideline_set = _set(client, admin)
    draft = client.post(
        f"/guidelines/admin/sets/{guideline_set['id']}/versions",
        json={"rubric_md": "## v1"},
        headers=admin,
    ).json()

    resp = client.put(
        f"/guidelines/admin/versions/{draft['id']}/source",
        files={"file": ("zarzadzenie.pdf", b"not a pdf", "application/pdf")},
        headers=admin,
    )

    assert resp.status_code == 422


def test_duplicate_university_is_a_conflict(client: TestClient) -> None:
    admin = _admin(client)
    body = {"name": "Uniwersytet Ekonomiczny w Katowicach", "short_name": "UE Katowice"}
    client.post("/guidelines/admin/universities", json=body, headers=admin)

    resp = client.post("/guidelines/admin/universities", json=body, headers=admin)

    assert resp.status_code == 409
