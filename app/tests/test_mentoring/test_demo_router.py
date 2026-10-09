"""The "load demo students" button: the seed script's roster, over HTTP."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from main import app
from src.mentoring.infrastructure.dependencies import get_agent_client
from tests.test_mentoring.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    PROMOTOR_EMAIL,
    PROMOTOR_PASSWORD,
    login,
)
from tests.test_mentoring.fakes import FakeAgentClient

DEMO_STUDENTS = 7


@pytest.fixture
def agent() -> Generator[FakeAgentClient, None, None]:
    fake = FakeAgentClient()
    app.dependency_overrides[get_agent_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_agent_client, None)


def test_a_promoter_gets_the_demo_students(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)

    resp = client.post("/students/demo", headers=headers)

    assert resp.status_code == 201, resp.text
    assert len(resp.json()["created"]) == DEMO_STUDENTS
    roster = client.get("/students", headers=headers).json()
    assert len(roster) == DEMO_STUDENTS


def test_loading_again_adds_only_the_ones_deleted(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    client.post("/students/demo", headers=headers)
    roster = client.get("/students", headers=headers).json()
    pawlak = next(s for s in roster if s["full_name"] == "Kazimierz Pawlak")
    assert (
        client.delete(f"/students/{pawlak['id']}", headers=headers).status_code == 204
    )

    body = client.post("/students/demo", headers=headers).json()

    assert body["created"] == ["Kazimierz Pawlak"]
    assert len(body["skipped"]) == DEMO_STUDENTS - 1


def test_demo_students_come_with_their_theses(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    client.post("/students/demo", headers=headers)
    roster = client.get("/students", headers=headers).json()
    kargul = next(s for s in roster if s["full_name"] == "Władysław Kargul")

    drafts = client.get(f"/students/{kargul['id']}/drafts", headers=headers).json()

    assert len(drafts) == 1


def test_an_admin_gets_no_demo_students(client: TestClient) -> None:
    """Admins hold no students (ADR 0008) — demo ones included."""
    headers = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

    assert client.post("/students/demo", headers=headers).status_code == 403


def test_demo_students_need_a_login(client: TestClient) -> None:
    assert client.post("/students/demo").status_code == 401
