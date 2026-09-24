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
from tests.test_mentoring.fakes import FakeAgentClient, topic_payload


@pytest.fixture(autouse=True)
def agent() -> Generator[FakeAgentClient, None, None]:
    """Every dashboard read checks unfinished actions with the agent."""
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


def _trigger(client: TestClient, headers: dict[str, str], student_id: str) -> str:
    resp = client.post(
        f"/students/{student_id}/actions",
        json={"action_type": "propose_topic"},
        headers=headers,
    )
    assert resp.status_code == 202, resp.text
    return str(resp.json()["id"])


def test_a_run_that_finished_unseen_is_not_counted(
    client: TestClient, agent: FakeAgentClient
) -> None:
    """Nobody opened the student, so our row still says pending — the agent knows."""
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    _trigger(client, headers, _new_student(client, headers))
    agent.completes_with(topic_payload("Instytucje a wzrost"))

    body = client.get("/dashboard/summary", headers=headers).json()

    assert body["actions_in_progress"] == 0
    assert body["recent_activity"][0]["status"] == "completed"


def test_actions_in_progress_lists_what_the_count_is_made_of(
    client: TestClient,
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers, full_name="Anna Nowak")
    action_id = _trigger(client, headers, student_id)

    resp = client.get("/dashboard/actions-in-progress", headers=headers)

    assert resp.status_code == 200, resp.text
    [item] = resp.json()
    assert item["id"] == action_id
    assert item["student_id"] == student_id
    assert item["student_name"] == "Anna Nowak"
    assert item["action_type"] == "propose_topic"
    assert item["created_at"]


def test_a_cancelled_action_leaves_the_list(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    action_id = _trigger(client, headers, student_id)

    resp = client.post(
        f"/students/{student_id}/actions/{action_id}/cancel", headers=headers
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "cancelled"
    assert agent.cancelled == ["task-1"]
    assert client.get("/dashboard/actions-in-progress", headers=headers).json() == []
    assert (
        client.get("/dashboard/summary", headers=headers).json()["actions_in_progress"]
        == 0
    )


def test_actions_in_progress_is_scoped_to_the_caller(client: TestClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    _trigger(client, headers, _new_student(client, headers))

    other = login(client, OTHER_PROMOTOR_EMAIL, OTHER_PROMOTOR_PASSWORD)

    assert client.get("/dashboard/actions-in-progress", headers=other).json() == []
