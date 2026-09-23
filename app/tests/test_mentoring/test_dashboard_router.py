"""Integration tests for the dashboard summary endpoint."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from main import app
from src.mentoring.infrastructure.dependencies import get_agent_client
from tests.test_mentoring.conftest import (
    OTHER_PROMOTOR_EMAIL,
    OTHER_PROMOTOR_PASSWORD,
    PROMOTOR_EMAIL,
    PROMOTOR_PASSWORD,
    login,
)
from tests.test_mentoring.fakes import FakeAgentClient


@pytest.fixture
def agent() -> Generator[FakeAgentClient, None, None]:
    fake = FakeAgentClient()
    app.dependency_overrides[get_agent_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_agent_client, None)


def _new_student(
    client: TestClient, headers: dict[str, str], **overrides: str
) -> str:
    body = {
        "full_name": "Jan Kowalski",
        "field_of_study": "Ekonomia",
        "thesis_type": "bachelor",
        **overrides,
    }
    resp = client.post("/students", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


def test_summary_counts_active_students_and_missing_topics(
    client: TestClient,
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    _new_student(client, headers, full_name="Anna Nowak")
    with_topic = _new_student(client, headers, full_name="Piotr Wiśniewski")
    client.patch(
        f"/students/{with_topic}",
        json={"current_topic": "Inflacja bazowa w Polsce"},
        headers=headers,
    )

    resp = client.get("/dashboard/summary", headers=headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["active_students"] == 2
    assert body["without_topic"] == 1


def test_summary_counts_actions_in_progress_and_lists_recent_activity(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers, full_name="Anna Nowak")
    client.post(
        f"/students/{student_id}/actions",
        json={"action_type": "propose_topic"},
        headers=headers,
    )

    body = client.get("/dashboard/summary", headers=headers).json()

    assert body["actions_in_progress"] == 1
    assert len(body["recent_activity"]) == 1
    assert body["recent_activity"][0]["student_name"] == "Anna Nowak"
    assert body["recent_activity"][0]["action_type"] == "propose_topic"
    assert body["recent_activity"][0]["status"] == "pending"


def test_summary_is_scoped_to_the_caller_own_students(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    _new_student(client, headers, full_name="Anna Nowak")

    other_headers = login(client, OTHER_PROMOTOR_EMAIL, OTHER_PROMOTOR_PASSWORD)
    body = client.get("/dashboard/summary", headers=other_headers).json()

    assert body["active_students"] == 0
    assert body["recent_activity"] == []
