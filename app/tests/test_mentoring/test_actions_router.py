"""Integration tests for the AI action endpoints."""

import uuid
from collections.abc import Generator
from typing import Any

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
from tests.test_mentoring.fakes import (
    FakeAgentClient,
    docx_bytes,
    note_payload,
    question_payload,
    topic_payload,
)

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
    resp = client.post(f"/students/{student_id}/actions", json=payload, headers=headers)
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


def test_action_without_the_data_it_needs_is_409(
    client: TestClient, agent: FakeAgentClient
) -> None:
    """A progress check on a student who uploaded nothing is a state conflict."""
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)

    resp = client.post(
        f"/students/{student_id}/actions",
        json={"action_type": "check_progress"},
        headers=headers,
    )
    assert resp.status_code == 409
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

    resp = client.get(f"/students/{student_id}/actions/{action['id']}", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["output"]["output"]["topics"][0]["title"] == "Instytucje a wzrost"


def test_polling_a_running_action_shows_its_progress(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    action = _trigger(client, headers, student_id)
    progress = {"steps": ["propose_topic"], "done": []}
    agent.runs_with(progress)

    body = client.get(
        f"/students/{student_id}/actions/{action['id']}", headers=headers
    ).json()

    assert body["status"] == "running"
    assert body["progress"] == progress


def test_a_finished_action_carries_no_progress(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    action = _trigger(client, headers, student_id)
    agent.completes_with(topic_payload("Instytucje a wzrost"))

    body = client.get(
        f"/students/{student_id}/actions/{action['id']}", headers=headers
    ).json()

    assert body["progress"] is None


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

    resp = client.get(f"/students/{student_id}/actions/{uuid.uuid4()}", headers=headers)
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


def test_cancelling_a_finished_action_is_409(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    action_id = _completed(client, headers, agent, student_id)

    resp = client.post(
        f"/students/{student_id}/actions/{action_id}/cancel", headers=headers
    )

    assert resp.status_code == 409
    assert agent.cancelled == []


def test_cancelling_another_promotors_action_is_404(
    client: TestClient, agent: FakeAgentClient
) -> None:
    theirs = login(client, OTHER_PROMOTOR_EMAIL, OTHER_PROMOTOR_PASSWORD)
    student_id = _new_student(client, theirs)
    action = _trigger(client, theirs, student_id)

    mine = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    resp = client.post(
        f"/students/{student_id}/actions/{action['id']}/cancel", headers=mine
    )

    assert resp.status_code == 404
    assert agent.cancelled == []


def test_deleting_an_action_takes_it_out_of_the_history(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    action = _trigger(client, headers, student_id)

    resp = client.delete(
        f"/students/{student_id}/actions/{action['id']}", headers=headers
    )

    assert resp.status_code == 204
    assert client.get(f"/students/{student_id}/actions", headers=headers).json() == []
    assert agent.deleted == ["task-1"]


def test_deleting_an_action_without_the_agent_is_503(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    action = _trigger(client, headers, student_id)
    agent.unavailable = True

    resp = client.delete(
        f"/students/{student_id}/actions/{action['id']}", headers=headers
    )

    assert resp.status_code == 503
    agent.unavailable = False
    listed = client.get(f"/students/{student_id}/actions", headers=headers).json()
    assert len(listed) == 1


def test_deleting_a_student_is_final(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    _trigger(client, headers, student_id)

    resp = client.delete(f"/students/{student_id}", headers=headers)

    assert resp.status_code == 204
    assert client.get(f"/students/{student_id}", headers=headers).status_code == 404
    assert [str(s) for s in agent.deleted_students] == [student_id]


def test_deleting_another_promotors_student_is_404(
    client: TestClient, agent: FakeAgentClient
) -> None:
    theirs = login(client, OTHER_PROMOTOR_EMAIL, OTHER_PROMOTOR_PASSWORD)
    student_id = _new_student(client, theirs)

    mine = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    resp = client.delete(f"/students/{student_id}", headers=mine)

    assert resp.status_code == 404
    assert client.get(f"/students/{student_id}", headers=theirs).status_code == 200


def test_deleting_a_student_without_the_agent_is_503(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    agent.unavailable = True

    resp = client.delete(f"/students/{student_id}", headers=headers)

    assert resp.status_code == 503
    assert client.get(f"/students/{student_id}", headers=headers).status_code == 200


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


# ---------- the rest of the catalog ----------


_DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _upload(client: TestClient, headers: dict[str, str], student_id: str) -> None:
    resp = client.post(
        f"/students/{student_id}/drafts",
        files={"file": ("praca.docx", docx_bytes("Rozdział 1: Wstęp."), _DOCX_TYPE)},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text


def test_defence_questions_run_against_the_uploaded_thesis(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    _upload(client, headers, student_id)

    action = _trigger(client, headers, student_id, action_type="defence_questions")
    agent.completes_with(
        question_payload(
            "Dlaczego wybrano tę metodę?",
            "Jak sformułowano problem badawczy?",
            "Jakie są ograniczenia wniosków?",
        )
    )
    resp = client.get(f"/students/{student_id}/actions/{action['id']}", headers=headers)

    body = resp.json()
    assert body["status"] == "completed"
    questions = body["output"]["output"]["questions"]
    assert len(questions) == 3
    assert questions[0]["question"] == "Dlaczego wybrano tę metodę?"
    assert "Rozdział 1" in agent.submitted[0]["context"]["text"]


def test_defence_questions_without_a_thesis_are_409(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)

    resp = client.post(
        f"/students/{student_id}/actions",
        json={"action_type": "defence_questions"},
        headers=headers,
    )

    assert resp.status_code == 409
    assert agent.submitted == []


def test_accepting_a_drafted_note_creates_the_note(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    action = _trigger(
        client,
        headers,
        student_id,
        action_type="draft_meeting_note",
        detail="rozdział 2, dobór próby, termin 15.03",
    )
    agent.completes_with(note_payload("Omówiliśmy zakres rozdziału 2."))
    client.get(f"/students/{student_id}/actions/{action['id']}", headers=headers)

    resp = client.patch(
        f"/students/{student_id}/actions/{action['id']}/accept",
        json={},
        headers=headers,
    )
    assert resp.status_code == 200

    notes = client.get(f"/students/{student_id}/meeting-notes", headers=headers).json()
    assert len(notes) == 1
    assert notes[0]["content"] == "Omówiliśmy zakres rozdziału 2."
    assert notes[0]["source_action_id"] == action["id"]


def test_review_action_is_queued_once_a_draft_exists(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    _upload(client, headers, student_id)

    body = _trigger(client, headers, student_id, action_type="generate_review")

    assert body["status"] == "pending"
    assert agent.submitted[0]["action_type"] == "generate_review"


def test_review_tone_reaches_the_assembled_context(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    _upload(client, headers, student_id)

    _trigger(
        client,
        headers,
        student_id,
        action_type="generate_review",
        review_tone="diplomatic",
    )

    assert agent.submitted[0]["context"]["review_tone"] == "diplomatic"


# ---------- a review paused for the promoter ----------


def _paused_review(
    client: TestClient, agent: FakeAgentClient, headers: dict[str, str]
) -> tuple[str, str]:
    student_id = _new_student(client, headers)
    _upload(client, headers, student_id)
    action = _trigger(
        client,
        headers,
        student_id,
        action_type="generate_review",
        review_findings_first=True,
    )
    agent.pauses_with(
        {
            "findings": [
                {"section": "Wstęp", "description": "Brak hipotez"},
                {"section": "Bibliografia", "description": "Za mało źródeł"},
            ]
        }
    )
    body = client.get(
        f"/students/{student_id}/actions/{action['id']}", headers=headers
    ).json()
    assert body["status"] == "awaiting_input"
    return student_id, action["id"]


def test_asking_to_see_findings_first_reaches_the_review_context(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    _paused_review(client, agent, headers)

    assert agent.submitted[0]["context"]["promoter_reviews_findings"] is True


def test_other_actions_never_pause(client: TestClient, agent: FakeAgentClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)

    _trigger(client, headers, student_id, review_findings_first=True)

    assert "promoter_reviews_findings" not in agent.submitted[0]["context"]


def test_resuming_sends_the_kept_findings_and_the_key_again(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    _store_key(client, headers, "claude", "sk-ant-user-key")
    student_id, action_id = _paused_review(client, agent, headers)

    resp = client.post(
        f"/students/{student_id}/actions/{action_id}/resume",
        json={"accepted_findings": [1, 1]},
        headers=headers,
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"
    sent = agent.resumed[0]
    assert sent["task_id"] == agent.task_id
    assert sent["decision"] == {"accepted": [1]}
    assert sent["byok"].api_key == "sk-ant-user-key"


def test_resuming_an_action_that_is_not_paused_is_409(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    action = _trigger(client, headers, student_id)

    resp = client.post(
        f"/students/{student_id}/actions/{action['id']}/resume",
        json={"accepted_findings": []},
        headers=headers,
    )

    assert resp.status_code == 409
    assert agent.resumed == []


def test_resuming_without_the_agent_is_503_and_stays_paused(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id, action_id = _paused_review(client, agent, headers)
    agent.unavailable = True

    resp = client.post(
        f"/students/{student_id}/actions/{action_id}/resume",
        json={"accepted_findings": [0]},
        headers=headers,
    )

    assert resp.status_code == 503
    agent.unavailable = False
    body = client.get(
        f"/students/{student_id}/actions/{action_id}", headers=headers
    ).json()
    assert body["status"] == "awaiting_input"


# ---------- the promoter's own key ----------


def _store_key(
    client: TestClient, headers: dict[str, str], provider: str, key: str
) -> None:
    resp = client.patch(
        "/settings/api-key",
        json={"api_key": key, "provider": provider},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text


def test_a_stored_key_is_used_for_the_run(
    client: TestClient, agent: FakeAgentClient
) -> None:
    """The promoter's own key, decrypted for this request and forwarded."""
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    _store_key(client, headers, "claude", "sk-ant-user-key")

    _trigger(client, headers, student_id)

    sent = agent.submitted[0]["byok"]
    assert sent is not None
    assert sent.provider == "claude"
    assert sent.api_key == "sk-ant-user-key"


def test_without_a_stored_key_the_run_stays_self_hosted(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)

    _trigger(client, headers, student_id)

    assert agent.submitted[0]["byok"] is None


def test_one_promotors_key_is_not_used_for_another(
    client: TestClient, agent: FakeAgentClient
) -> None:
    """Keys are per user: whoever triggers the action pays for it."""
    theirs = login(client, OTHER_PROMOTOR_EMAIL, OTHER_PROMOTOR_PASSWORD)
    _store_key(client, theirs, "openai", "sk-openai-their-key")

    mine = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, mine)
    _trigger(client, mine, student_id)

    assert agent.submitted[0]["byok"] is None


def test_the_key_never_appears_in_the_action_response(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    _store_key(client, headers, "claude", "sk-ant-user-key")

    resp = client.post(
        f"/students/{student_id}/actions",
        json={"action_type": "propose_topic"},
        headers=headers,
    )
    assert resp.status_code == 202
    assert "sk-ant-user-key" not in resp.text

    history = client.get(f"/students/{student_id}/actions", headers=headers)
    assert "sk-ant-user-key" not in history.text
