"""Integration tests for the AI action endpoints."""

import uuid
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from main import app
from src.mentoring.infrastructure.router import get_agent_client
from tests.test_mentoring.conftest import (
    OTHER_PROMOTOR_EMAIL,
    OTHER_PROMOTOR_PASSWORD,
    PROMOTOR_EMAIL,
    PROMOTOR_PASSWORD,
    login,
)
from tests.test_mentoring.fakes import FakeAgentClient, topic_payload

_STUDENT: dict[str, Any] = {
    "full_name": "Jan Kowalski",
    "field_of_study": "Ekonomia",
    "thesis_type": "bachelor",
}


@pytest.fixture
def agent() -> Generator[FakeAgentClient, None, None]:
    """Swap the real agent client for one that never leaves the process."""
    fake = FakeAgentClient()
    app.dependency_overrides[get_agent_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_agent_client, None)


def _new_student(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post("/students", json=_STUDENT, headers=headers)
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


def _trigger(
    client: TestClient, headers: dict[str, str], student_id: str, **body: object
) -> dict[str, Any]:
    payload = {"action_type": "propose_topic", **body}
    resp = client.post(
        f"/students/{student_id}/actions", json=payload, headers=headers
    )
    assert resp.status_code == 202, resp.text
    result: dict[str, Any] = resp.json()
    return result


# ---------- trigger ----------


def test_trigger_returns_the_queued_action(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)

    body = _trigger(client, headers, student_id, detail="coś ilościowego")

    assert body["status"] == "pending"
    assert body["action_type"] == "propose_topic"
    assert body["task_id"] == agent.task_id
    assert body["accepted"] is False
    assert agent.submitted[0]["student_id"] == uuid.UUID(student_id)


def test_trigger_forwards_the_callers_token(
    client: TestClient, agent: FakeAgentClient
) -> None:
    """The agent does its own auth, so it must get the promoter's token."""
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)

    _trigger(client, headers, student_id)

    assert headers["Authorization"].endswith(agent.submitted[0]["token"])


def test_trigger_requires_auth(client: TestClient, agent: FakeAgentClient) -> None:
    resp = client.post(
        f"/students/{uuid.uuid4()}/actions", json={"action_type": "propose_topic"}
    )
    assert resp.status_code == 401


def test_trigger_on_another_promotors_student_is_404(
    client: TestClient, agent: FakeAgentClient
) -> None:
    theirs = login(client, OTHER_PROMOTOR_EMAIL, OTHER_PROMOTOR_PASSWORD)
    student_id = _new_student(client, theirs)

    mine = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    resp = client.post(
        f"/students/{student_id}/actions",
        json={"action_type": "propose_topic"},
        headers=mine,
    )
    assert resp.status_code == 404


def test_unknown_action_type_is_rejected(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)

    resp = client.post(
        f"/students/{student_id}/actions",
        json={"action_type": "write_the_whole_thesis"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_action_awaiting_phase_three_is_rejected(
    client: TestClient, agent: FakeAgentClient
) -> None:
    """A valid action type with no context assembly yet must not be queued."""
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)

    resp = client.post(
        f"/students/{student_id}/actions",
        json={"action_type": "check_progress"},
        headers=headers,
    )
    assert resp.status_code == 422
    assert agent.submitted == []


def test_unavailable_agent_reports_503(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    agent.unavailable = True

    resp = client.post(
        f"/students/{student_id}/actions",
        json={"action_type": "propose_topic"},
        headers=headers,
    )
    assert resp.status_code == 503

    history = client.get(f"/students/{student_id}/actions", headers=headers).json()
    assert history[0]["status"] == "failed"


# ---------- poll and list ----------


def test_polling_reflects_the_finished_action(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    action = _trigger(client, headers, student_id)
    agent.completes_with(topic_payload("Instytucje a wzrost", "Kapitał społeczny"))

    resp = client.get(
        f"/students/{student_id}/actions/{action['id']}", headers=headers
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["output"]["output"]["topics"][0]["title"] == "Instytucje a wzrost"


def test_list_actions_shows_the_history(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    _trigger(client, headers, student_id)

    resp = client.get(
        f"/students/{student_id}/actions?type=propose_topic", headers=headers
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_unknown_action_is_404(client: TestClient, agent: FakeAgentClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)

    resp = client.get(
        f"/students/{student_id}/actions/{uuid.uuid4()}", headers=headers
    )
    assert resp.status_code == 404


# ---------- accept ----------


def _completed(
    client: TestClient, headers: dict[str, str], agent: FakeAgentClient, sid: str
) -> str:
    action = _trigger(client, headers, sid)
    agent.completes_with(topic_payload("Instytucje a wzrost", "Kapitał społeczny"))
    client.get(f"/students/{sid}/actions/{action['id']}", headers=headers)
    return str(action["id"])


def test_accepting_sets_the_students_topic(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    action_id = _completed(client, headers, agent, student_id)

    resp = client.patch(
        f"/students/{student_id}/actions/{action_id}/accept",
        json={"topic_index": 1},
        headers=headers,
    )

    assert resp.status_code == 200
    assert resp.json()["accepted"] is True
    student = client.get(f"/students/{student_id}", headers=headers).json()
    assert student["current_topic"] == "Kapitał społeczny"
    assert student["current_topic_set_at"] is not None


def test_accepting_an_unfinished_action_is_409(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    action = _trigger(client, headers, student_id)

    resp = client.patch(
        f"/students/{student_id}/actions/{action['id']}/accept",
        json={},
        headers=headers,
    )
    assert resp.status_code == 409


def test_accepting_a_topic_nobody_proposed_is_409(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    action_id = _completed(client, headers, agent, student_id)

    resp = client.patch(
        f"/students/{student_id}/actions/{action_id}/accept",
        json={"topic_index": 9},
        headers=headers,
    )
    assert resp.status_code == 409

    student = client.get(f"/students/{student_id}", headers=headers).json()
    assert student["current_topic"] is None
