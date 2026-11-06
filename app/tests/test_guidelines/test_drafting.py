"""A rubric drafted by the model from an uploaded regulation (ADR 0025)."""

import uuid
from collections.abc import Generator
from typing import Any

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from src.guidelines.application.exceptions import DrafterUnavailableError
from src.guidelines.application.rubric_drafting import (
    DraftingStatus,
    ProviderKey,
    RubricDraftingService,
)
from src.guidelines.domain.rubric import parse_rubric
from src.guidelines.infrastructure.dependencies import get_drafting_service
from src.guidelines.infrastructure.orm import SourceFileModel
from src.guidelines.infrastructure.repositories import CatalogRepository
from src.mentoring.infrastructure.dependencies import get_agent_client
from src.shared.database import get_db_session
from src.shared.sql_file_store import SqlFileStore
from tests.rubrics import rubric
from tests.test_mentoring.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, login
from tests.test_mentoring.fakes import FakeAgentClient, docx_bytes

_DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

_OUTPUT: dict[str, Any] = {
    "elements": "### Wstęp\n- cel pracy (§ 3 ust. 2)",
    "formal": "Liczby są w progach wersji.\n### Objętość\n- sugerowana (§ 4 ust. 5)",
    "merit": "- logiczny tok wywodu (§ 2 ust. 2)",
    "severity": "Interpretacja Corvusa.\n### CRITICAL — blokuje\n- brak wstępu",
    "thresholds": {
        "min_sources": 25,
        "min_foreign_sources": 4,
        "min_body_chars": 80000,
        "max_body_chars": 130000,
    },
    "doubts": ["Załącznik nr 3 nie został dołączony."],
}


class FakeDrafter:
    """The agent, answering whatever the test sets."""

    def __init__(self) -> None:
        self.submitted: list[dict[str, Any]] = []
        self.answer = DraftingStatus(status="running", output=None, error=None)
        self.down = False

    async def submit(
        self,
        version_id: uuid.UUID,
        context: dict[str, Any],
        key: ProviderKey,
        token: str,
    ) -> str:
        if self.down:
            raise DrafterUnavailableError("agent down")
        self.submitted.append(
            {"version_id": version_id, "context": context, "key": key}
        )
        return "task-1"

    async def status(self, task_id: str, token: str) -> DraftingStatus:
        return self.answer


@pytest.fixture
def drafter() -> Generator[FakeDrafter, None, None]:
    fake = FakeDrafter()

    def _service(
        session: AsyncSession = Depends(get_db_session),  # noqa: B008
    ) -> RubricDraftingService:
        return RubricDraftingService(
            CatalogRepository(session), SqlFileStore(session, SourceFileModel), fake
        )

    app.dependency_overrides[get_drafting_service] = _service
    yield fake
    app.dependency_overrides.pop(get_drafting_service, None)


@pytest.fixture
def admin(client: TestClient) -> dict[str, str]:
    headers = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    resp = client.patch(
        "/settings/api-key",
        json={"api_key": "sk-ant-admin-key", "provider": "claude"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return headers


def _draft_with_source(
    client: TestClient, admin: dict[str, str], thesis_type: str = "bachelor"
) -> str:
    universities = client.get("/guidelines/universities", headers=admin).json()
    university = (
        universities[0]
        if universities
        else client.post(
            "/guidelines/admin/universities",
            json={"name": "Uniwersytet Testowy", "short_name": "UT"},
            headers=admin,
        ).json()
    )
    guideline_set = client.post(
        "/guidelines/admin/sets",
        json={
            "university_id": university["id"],
            "thesis_type": thesis_type,
            "name": f"Wytyczne {thesis_type} {uuid.uuid4().hex[:4]}",
        },
        headers=admin,
    ).json()
    draft = client.post(
        f"/guidelines/admin/sets/{guideline_set['id']}/versions",
        json={},
        headers=admin,
    ).json()
    attached = client.put(
        f"/guidelines/admin/versions/{draft['id']}/source",
        files={
            "file": (
                "Zarządzenie.docx",
                docx_bytes("§ 4. Praca opiera się na co najmniej 25 pozycjach."),
                _DOCX_TYPE,
            )
        },
        headers=admin,
    )
    assert attached.status_code == 200, attached.text
    return str(draft["id"])


def _start(client: TestClient, admin: dict[str, str], version_id: str) -> Any:  # noqa: ANN401
    return client.post(
        f"/guidelines/admin/versions/{version_id}/draft-rubric",
        json={"provider": "claude"},
        headers=admin,
    )


def test_the_regulation_goes_to_the_model_on_the_admins_key(
    client: TestClient, admin: dict[str, str], drafter: FakeDrafter
) -> None:
    version_id = _draft_with_source(client, admin)

    resp = _start(client, admin, version_id)

    assert resp.status_code == 202, resp.text
    assert resp.json()["drafting"] is True
    sent = drafter.submitted[0]
    assert "co najmniej 25 pozycjach" in sent["context"]["regulation"]
    assert sent["context"]["thesis_type"] == "bachelor"
    assert sent["context"]["regulation_filename"] == "Zarządzenie.docx"
    assert sent["key"] == ProviderKey("claude", "sk-ant-admin-key")
    assert "example_rubric" not in sent["context"]


def test_another_sets_published_rubric_goes_along_as_a_model(
    client: TestClient, admin: dict[str, str], drafter: FakeDrafter
) -> None:
    published = _draft_with_source(client, admin)
    client.patch(
        f"/guidelines/admin/versions/{published}",
        json={"rubric_md": rubric("wzór")},
        headers=admin,
    )
    client.post(f"/guidelines/admin/versions/{published}/publish", headers=admin)
    version_id = _draft_with_source(client, admin)

    _start(client, admin, version_id)

    assert drafter.submitted[0]["context"]["example_rubric"] == rubric("wzór")


def test_while_the_model_reads_the_draft_waits_and_cannot_change(
    client: TestClient, admin: dict[str, str], drafter: FakeDrafter
) -> None:
    version_id = _draft_with_source(client, admin)
    _start(client, admin, version_id)

    read = client.get(f"/guidelines/admin/versions/{version_id}", headers=admin)
    edited = client.patch(
        f"/guidelines/admin/versions/{version_id}",
        json={"rubric_md": rubric()},
        headers=admin,
    )
    published = client.post(
        f"/guidelines/admin/versions/{version_id}/publish", headers=admin
    )
    again = _start(client, admin, version_id)

    assert read.json()["drafting"] is True
    assert edited.status_code == 409
    assert published.status_code == 409
    assert again.status_code == 409


def test_a_finished_draft_fills_the_version_and_can_be_published(
    client: TestClient, admin: dict[str, str], drafter: FakeDrafter
) -> None:
    version_id = _draft_with_source(client, admin)
    _start(client, admin, version_id)
    drafter.answer = DraftingStatus(status="completed", output=_OUTPUT, error=None)

    version = client.get(
        f"/guidelines/admin/versions/{version_id}", headers=admin
    ).json()
    published = client.post(
        f"/guidelines/admin/versions/{version_id}/publish", headers=admin
    )

    assert version["drafting"] is False
    assert version["thresholds"]["min_sources"] == 25
    assert version["thresholds"]["max_body_chars"] == 130000
    sections = parse_rubric(version["rubric_md"])
    assert sections.elements == "### Wstęp\n- cel pracy (§ 3 ust. 2)"
    # What to check sits beside the rubric, never in what a model is given.
    assert version["draft_notes"] == ["Załącznik nr 3 nie został dołączony."]
    assert "Załącznik" not in version["rubric_md"]
    assert version["rubric_md"].startswith("## Elementy pracy")
    assert published.status_code == 200, published.text
    assert published.json()["draft_notes"] == []


def test_a_failed_run_says_why_and_leaves_the_draft_as_it_was(
    client: TestClient, admin: dict[str, str], drafter: FakeDrafter
) -> None:
    version_id = _draft_with_source(client, admin)
    _start(client, admin, version_id)
    drafter.answer = DraftingStatus(status="failed", output=None, error="no credits")

    version = client.get(
        f"/guidelines/admin/versions/{version_id}", headers=admin
    ).json()

    assert version["drafting"] is False
    assert version["drafting_error"] == "no credits"
    assert version["rubric_md"] == ""
    assert _start(client, admin, version_id).status_code == 202


def test_a_reply_that_breaks_the_sections_is_not_taken_in(
    client: TestClient, admin: dict[str, str], drafter: FakeDrafter
) -> None:
    version_id = _draft_with_source(client, admin)
    _start(client, admin, version_id)
    broken = {**_OUTPUT, "merit": "## Inne\n- coś"}
    drafter.answer = DraftingStatus(status="completed", output=broken, error=None)

    version = client.get(
        f"/guidelines/admin/versions/{version_id}", headers=admin
    ).json()

    assert version["drafting"] is False
    assert "could not be used" in version["drafting_error"]
    assert version["rubric_md"] == ""


def test_thresholds_that_contradict_each_other_become_a_doubt(
    client: TestClient, admin: dict[str, str], drafter: FakeDrafter
) -> None:
    version_id = _draft_with_source(client, admin)
    _start(client, admin, version_id)
    odd = {**_OUTPUT, "thresholds": {"min_sources": 4, "min_foreign_sources": 25}}
    drafter.answer = DraftingStatus(status="completed", output=odd, error=None)

    version = client.get(
        f"/guidelines/admin/versions/{version_id}", headers=admin
    ).json()

    assert version["thresholds"]["min_sources"] is None
    assert any("Progi z regulaminu" in note for note in version["draft_notes"])


def test_without_a_key_for_the_provider_nothing_is_sent(
    client: TestClient, admin: dict[str, str], drafter: FakeDrafter
) -> None:
    version_id = _draft_with_source(client, admin)

    resp = client.post(
        f"/guidelines/admin/versions/{version_id}/draft-rubric",
        json={"provider": "openai"},
        headers=admin,
    )

    assert resp.status_code == 409
    assert "openai" in resp.json()["detail"]
    assert drafter.submitted == []


def test_without_a_regulation_there_is_nothing_to_draft_from(
    client: TestClient, admin: dict[str, str], drafter: FakeDrafter
) -> None:
    university = client.post(
        "/guidelines/admin/universities",
        json={"name": "Uniwersytet Bez Pliku", "short_name": "UBP"},
        headers=admin,
    ).json()
    guideline_set = client.post(
        "/guidelines/admin/sets",
        json={
            "university_id": university["id"],
            "thesis_type": "bachelor",
            "name": "X",
        },
        headers=admin,
    ).json()
    empty = client.post(
        f"/guidelines/admin/sets/{guideline_set['id']}/versions", json={}, headers=admin
    ).json()

    resp = _start(client, admin, empty["id"])

    assert resp.status_code == 422
    assert "Attach the regulation" in resp.json()["detail"]
    assert drafter.submitted == []


def test_an_agent_that_does_not_answer_is_503_and_the_draft_is_free(
    client: TestClient, admin: dict[str, str], drafter: FakeDrafter
) -> None:
    version_id = _draft_with_source(client, admin)
    drafter.down = True

    resp = _start(client, admin, version_id)
    read = client.get(f"/guidelines/admin/versions/{version_id}", headers=admin)

    assert resp.status_code == 503
    assert read.json()["drafting"] is False


def test_a_promoter_cannot_draft(
    client: TestClient, admin: dict[str, str], drafter: FakeDrafter
) -> None:
    from tests.test_mentoring.conftest import PROMOTOR_EMAIL, PROMOTOR_PASSWORD

    version_id = _draft_with_source(client, admin)
    promotor = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)

    assert _start(client, promotor, version_id).status_code == 403


def test_a_length_in_pages_lands_in_the_page_thresholds(
    client: TestClient, admin: dict[str, str], drafter: FakeDrafter
) -> None:
    version_id = _draft_with_source(client, admin)
    _start(client, admin, version_id)
    pages = {
        **_OUTPUT,
        "thresholds": {"min_sources": 15, "min_pages": 40, "max_pages": 60},
    }
    drafter.answer = DraftingStatus(status="completed", output=pages, error=None)

    version = client.get(
        f"/guidelines/admin/versions/{version_id}", headers=admin
    ).json()

    assert version["thresholds"]["min_pages"] == 40
    assert version["thresholds"]["max_pages"] == 60
    assert version["thresholds"]["min_body_chars"] is None


# ---------- correcting, discarding, starting again ----------


def _published(client: TestClient, admin: dict[str, str]) -> tuple[str, str]:
    """A set with a published version that has its regulation; (set, version)."""
    version_id = _draft_with_source(client, admin)
    client.patch(
        f"/guidelines/admin/versions/{version_id}",
        json={"rubric_md": rubric("v1"), "thresholds": {"min_sources": 25}},
        headers=admin,
    )
    published = client.post(
        f"/guidelines/admin/versions/{version_id}/publish", headers=admin
    ).json()
    return str(published["set_id"]), version_id


def test_a_correction_starts_from_the_published_version_and_its_regulation(
    client: TestClient, admin: dict[str, str]
) -> None:
    set_id, published_id = _published(client, admin)

    resp = client.post(f"/guidelines/admin/sets/{set_id}/corrections", headers=admin)
    corrected = client.patch(
        f"/guidelines/admin/versions/{resp.json()['id']}",
        json={"rubric_md": rubric("v2")},
        headers=admin,
    )

    assert resp.status_code == 201, resp.text
    draft = resp.json()
    assert draft["version_no"] == 2
    assert draft["rubric_md"] == rubric("v1")
    assert draft["thresholds"]["min_sources"] == 25
    assert draft["source"]["filename"] == "Zarządzenie.docx"
    assert corrected.status_code == 200
    # The published version is untouched, and keeps its own original.
    old = client.get(f"/guidelines/versions/{published_id}", headers=admin).json()
    assert old["rubric_md"] == rubric("v1")
    assert (
        client.get(
            f"/guidelines/versions/{published_id}/source", headers=admin
        ).status_code
        == 200
    )


def test_a_discarded_draft_goes_and_the_published_version_stays(
    client: TestClient, admin: dict[str, str]
) -> None:
    set_id, published_id = _published(client, admin)
    draft = client.post(
        f"/guidelines/admin/sets/{set_id}/corrections", headers=admin
    ).json()

    resp = client.delete(f"/guidelines/admin/versions/{draft['id']}", headers=admin)

    assert resp.status_code == 204
    detail = client.get(f"/guidelines/sets/{set_id}", headers=admin).json()
    assert [v["id"] for v in detail["versions"]] == [published_id]
    assert (
        client.get(
            f"/guidelines/versions/{published_id}/source", headers=admin
        ).status_code
        == 200
    )
    again = client.post(f"/guidelines/admin/sets/{set_id}/corrections", headers=admin)
    assert again.status_code == 201


def test_a_published_version_cannot_be_discarded(
    client: TestClient, admin: dict[str, str]
) -> None:
    _, published_id = _published(client, admin)

    resp = client.delete(f"/guidelines/admin/versions/{published_id}", headers=admin)

    assert resp.status_code == 409


def test_a_deleted_set_is_gone_and_its_students_must_pick_again(
    client: TestClient, admin: dict[str, str]
) -> None:
    from tests.test_mentoring.conftest import PROMOTOR_EMAIL, PROMOTOR_PASSWORD

    set_id, published_id = _published(client, admin)
    promotor = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student = client.post(
        "/students",
        json={
            "full_name": "Jan",
            "field_of_study": "Ekonomia",
            "thesis_type": "bachelor",
            "guideline_set_id": set_id,
        },
        headers=promotor,
    ).json()
    client.post(
        f"/students/{student['id']}/drafts",
        files={"file": ("praca.docx", docx_bytes("Tekst pracy."), _DOCX_TYPE)},
        headers=promotor,
    )

    resp = client.delete(f"/guidelines/admin/sets/{set_id}", headers=admin)
    app.dependency_overrides[get_agent_client] = FakeAgentClient
    try:
        review = client.post(
            f"/students/{student['id']}/actions",
            json={"provider": "claude", "action_type": "trial_review"},
            headers=promotor,
        )
    finally:
        app.dependency_overrides.pop(get_agent_client, None)

    assert resp.status_code == 204
    assert client.get(f"/guidelines/sets/{set_id}", headers=admin).status_code == 404
    assert (
        client.get(f"/guidelines/versions/{published_id}", headers=admin).status_code
        == 404
    )
    assert review.status_code == 409
    assert "guidelines" in review.json()["detail"]


def test_a_promoter_cannot_delete_a_set(
    client: TestClient, admin: dict[str, str]
) -> None:
    from tests.test_mentoring.conftest import PROMOTOR_EMAIL, PROMOTOR_PASSWORD

    set_id, _ = _published(client, admin)
    promotor = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)

    assert (
        client.delete(f"/guidelines/admin/sets/{set_id}", headers=promotor).status_code
        == 403
    )
