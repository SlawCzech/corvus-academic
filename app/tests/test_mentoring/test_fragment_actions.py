"""Integration tests for running `review_fragment` on a fragment."""

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
from tests.test_mentoring.fakes import FakeAgentClient

_STUDENT: dict[str, Any] = {
    "full_name": "Jan Kowalski",
    "field_of_study": "Ekonomia",
    "thesis_type": "bachelor",
}


@pytest.fixture
def agent() -> Generator[FakeAgentClient, None, None]:
    fake = FakeAgentClient()
    app.dependency_overrides[get_agent_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_agent_client, None)


def _new_student(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post("/students", json=_STUDENT, headers=headers)
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


def _paste(
    client: TestClient,
    headers: dict[str, str],
    student_id: str,
    part_name: str = "Rozdział 1",
    text: str = "Przegląd literatury.",
    **fields: str,
) -> dict[str, Any]:
    resp = client.post(
        f"/students/{student_id}/fragments",
        data={"part_name": part_name, "text": text, **fields},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    result: dict[str, Any] = resp.json()
    return result


def _review(
    client: TestClient,
    headers: dict[str, str],
    student_id: str,
    fragment_id: str | None,
) -> Any:  # noqa: ANN401
    return client.post(
        f"/students/{student_id}/actions",
        json={
            "provider": "claude",
            "action_type": "review_fragment",
            "fragment_id": fragment_id,
        },
        headers=headers,
    )


def test_a_review_reads_the_fragment_and_not_the_rubric(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    fragment = _paste(client, headers, student_id, question="Czy to dobry kierunek?")

    resp = _review(client, headers, student_id, fragment["id"])

    assert resp.status_code == 202, resp.text
    context = agent.submitted[-1]["context"]
    assert context["text"] == "Przegląd literatury."
    assert context["part_name"] == "Rozdział 1"
    assert context["round_number"] == 1
    assert context["detail"] == "Czy to dobry kierunek?"
    assert context["field_of_study"] == "Ekonomia"
    assert "guidelines" not in context
    assert "previous_text" not in context


def test_a_later_round_gets_the_one_before_it(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    _paste(client, headers, student_id, text="Pierwsza runda.")
    second = _paste(client, headers, student_id, text="Druga runda.")

    _review(client, headers, student_id, second["id"])

    context = agent.submitted[-1]["context"]
    assert context["round_number"] == 2
    assert context["previous_text"] == "Pierwsza runda."
    assert context["previous_verdict"] is None


def test_the_other_parts_come_with_where_they_stand(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    client.post(
        f"/students/{student_id}/parts", json={"name": "Wstęp"}, headers=headers
    )
    _paste(client, headers, student_id, part_name="Rozdział 1")
    fragment = _paste(client, headers, student_id, part_name="Rozdział 2")

    _review(client, headers, student_id, fragment["id"])

    assert agent.submitted[-1]["context"]["other_parts"] == [
        {"name": "Wstęp", "state": "not_submitted"},
        {"name": "Rozdział 1", "state": "awaiting_feedback"},
    ]


def test_a_review_needs_a_fragment(client: TestClient, agent: FakeAgentClient) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)

    resp = _review(client, headers, student_id, None)

    assert resp.status_code == 422
    assert agent.submitted == []


def test_a_fragment_of_another_student_is_not_found(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    first = _new_student(client, headers)
    second = _new_student(client, headers)
    fragment = _paste(client, headers, first)

    assert _review(client, headers, second, fragment["id"]).status_code == 404
    assert agent.submitted == []


def test_another_promoter_cannot_run_it(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    other = login(client, OTHER_PROMOTOR_EMAIL, OTHER_PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    fragment = _paste(client, headers, student_id)

    assert _review(client, other, student_id, fragment["id"]).status_code == 404


def test_full_thesis_actions_still_read_only_whole_versions(
    client: TestClient, agent: FakeAgentClient
) -> None:
    """A fragment must not silently become "the thesis"."""
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    _paste(client, headers, student_id)

    resp = client.post(
        f"/students/{student_id}/actions",
        json={"provider": "claude", "action_type": "generate_review"},
        headers=headers,
    )

    assert resp.status_code == 409
    assert agent.submitted == []


def _summary_payload(text: str = "Fragment omawia literaturę.") -> dict[str, Any]:
    return {"output": {"summary": text, "direction": "on_track"}, "summary": text}


def test_feedback_is_saved_and_can_be_corrected(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    fragment = _paste(client, headers, student_id)
    url = f"/students/{student_id}/fragments/{fragment['id']}/feedback"

    first = client.put(
        url,
        json={"verdict": "needs_changes", "feedback": "Dodaj próbę."},
        headers=headers,
    )
    second = client.put(url, json={"verdict": "on_track"}, headers=headers)

    assert first.status_code == 200, first.text
    assert first.json()["feedback"] == "Dodaj próbę."
    assert second.json()["verdict"] == "on_track"
    assert second.json()["feedback"] is None


def test_an_unknown_verdict_is_refused(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    fragment = _paste(client, headers, student_id)

    resp = client.put(
        f"/students/{student_id}/fragments/{fragment['id']}/feedback",
        json={"verdict": "excellent"},
        headers=headers,
    )

    assert resp.status_code == 422


def test_feedback_from_the_draft_marks_the_run_accepted(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    fragment = _paste(client, headers, student_id)
    run = _review(client, headers, student_id, fragment["id"]).json()
    agent.completes_with(_summary_payload())
    client.get(f"/students/{student_id}/actions/{run['id']}", headers=headers)
    url = f"/students/{student_id}/fragments/{fragment['id']}/feedback"
    body = {"verdict": "on_track", "source_action_id": run["id"]}

    resp = client.put(url, json=body, headers=headers)
    again = client.put(url, json=body, headers=headers)

    assert resp.status_code == 200, resp.text
    assert again.status_code == 200
    action = client.get(
        f"/students/{student_id}/actions/{run['id']}", headers=headers
    ).json()
    assert action["accepted"] is True


def test_feedback_cannot_cite_a_run_that_is_not_the_fragments_latest(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    first = _paste(client, headers, student_id)
    second = _paste(client, headers, student_id)
    run = _review(client, headers, student_id, first["id"]).json()

    resp = client.put(
        f"/students/{student_id}/fragments/{second['id']}/feedback",
        json={"verdict": "on_track", "source_action_id": run["id"]},
        headers=headers,
    )

    assert resp.status_code == 422


def test_next_due_on_sets_the_deadline_of_the_part(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    fragment = _paste(client, headers, student_id)

    client.put(
        f"/students/{student_id}/fragments/{fragment['id']}/feedback",
        json={"verdict": "needs_changes", "next_due_on": "2026-11-14"},
        headers=headers,
    )

    timeline = client.get(f"/students/{student_id}/timeline", headers=headers).json()
    assert timeline["parts"][0]["due_on"] == "2026-11-14"
    assert timeline["parts"][0]["state"] == "needs_changes"
    assert timeline["parts"][0]["rounds"] == 1


def test_the_second_round_hears_the_feedback_on_the_first(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    first = _paste(client, headers, student_id)
    client.put(
        f"/students/{student_id}/fragments/{first['id']}/feedback",
        json={"verdict": "needs_changes", "feedback": "Uzasadnij dobór próby."},
        headers=headers,
    )
    second = _paste(client, headers, student_id)

    _review(client, headers, student_id, second["id"])

    context = agent.submitted[-1]["context"]
    assert context["previous_verdict"] == "needs_changes"
    assert context["previous_feedback"] == "Uzasadnij dobór próby."


def test_the_timeline_merges_what_happened_newest_first(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    client.post(
        f"/students/{student_id}/meeting-notes",
        json={
            "occurred_at": "2026-10-10T10:00:00Z",
            "content": "Ustalono zakres.",
        },
        headers=headers,
    )
    _paste(client, headers, student_id, received_on="2026-10-20")
    _paste(client, headers, student_id, part_name="Wstęp", received_on="2026-10-01")

    timeline = client.get(f"/students/{student_id}/timeline", headers=headers).json()

    assert [e["on"] for e in timeline["events"]] == [
        "2026-10-20",
        "2026-10-10",
        "2026-10-01",
    ]
    assert [e["kind"] for e in timeline["events"]] == ["fragment", "note", "fragment"]
    assert timeline["events"][0]["fragment"]["part_name"] == "Rozdział 1"
    assert timeline["events"][0]["fragment"]["summary"] is None
    assert "Przegląd" in timeline["events"][0]["fragment"]["preview"]


def test_the_summary_appears_once_the_run_is_finished(
    client: TestClient, agent: FakeAgentClient
) -> None:
    """Without anyone polling the run: the promoter may have left the page."""
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    fragment = _paste(client, headers, student_id)
    run = _review(client, headers, student_id, fragment["id"]).json()
    agent.completes_with(_summary_payload("Fragment omawia teorię."))

    timeline = client.get(f"/students/{student_id}/timeline", headers=headers).json()

    entry = timeline["events"][0]["fragment"]
    assert entry["review_action_id"] == run["id"]
    assert entry["summary"] == "Fragment omawia teorię."
    assert entry["review"]["status"] == "completed"


def test_a_new_run_replaces_the_one_the_fragment_shows(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    fragment = _paste(client, headers, student_id)
    _review(client, headers, student_id, fragment["id"])

    second = _review(client, headers, student_id, fragment["id"]).json()

    timeline = client.get(f"/students/{student_id}/timeline", headers=headers).json()
    assert timeline["events"][0]["fragment"]["review_action_id"] == second["id"]


def test_deleting_a_fragment_takes_its_file_and_runs_with_it(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    fragment = _paste(client, headers, student_id)
    run = _review(client, headers, student_id, fragment["id"]).json()
    url = f"/students/{student_id}"

    assert (
        client.delete(f"{url}/fragments/{fragment['id']}", headers=headers).status_code
        == 204
    )

    assert agent.deleted == [agent.task_id]
    assert client.get(f"{url}/actions/{run['id']}", headers=headers).status_code == 404
    assert client.get(f"{url}/timeline", headers=headers).json()["events"] == []
    replacement = _paste(client, headers, student_id)
    assert replacement["round_number"] == 1


def test_a_fragment_stays_when_the_agent_cannot_forget_its_runs(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    fragment = _paste(client, headers, student_id)
    _review(client, headers, student_id, fragment["id"])
    agent.unavailable = True

    resp = client.delete(
        f"/students/{student_id}/fragments/{fragment['id']}", headers=headers
    )

    assert resp.status_code == 503
    agent.unavailable = False
    timeline = client.get(f"/students/{student_id}/timeline", headers=headers).json()
    assert len(timeline["events"]) == 1


def test_another_promoter_reaches_neither_feedback_nor_timeline(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    other = login(client, OTHER_PROMOTOR_EMAIL, OTHER_PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    fragment = _paste(client, headers, student_id)
    url = f"/students/{student_id}"

    assert client.get(f"{url}/timeline", headers=other).status_code == 404
    assert (
        client.put(
            f"{url}/fragments/{fragment['id']}/feedback",
            json={"verdict": "on_track"},
            headers=other,
        ).status_code
        == 404
    )
    assert (
        client.delete(f"{url}/fragments/{fragment['id']}", headers=other).status_code
        == 404
    )


def test_the_dashboard_lists_what_waits_and_what_is_overdue(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    waiting = _paste(client, headers, student_id, part_name="Rozdział 1")
    answered = _paste(client, headers, student_id, part_name="Rozdział 2")
    client.put(
        f"/students/{student_id}/fragments/{answered['id']}/feedback",
        json={"verdict": "on_track"},
        headers=headers,
    )
    parts = f"/students/{student_id}/parts"
    for name, due_on in (("Rozdział 3", "2020-01-01"), ("Rozdział 4", "2999-01-01")):
        client.post(parts, json={"name": name, "due_on": due_on}, headers=headers)

    summary = client.get("/dashboard/summary", headers=headers).json()

    assert [f["fragment_id"] for f in summary["awaiting_feedback"]] == [waiting["id"]]
    assert summary["awaiting_feedback"][0]["student_name"] == "Jan Kowalski"
    assert summary["awaiting_feedback"][0]["part_name"] == "Rozdział 1"
    assert [p["part_name"] for p in summary["overdue_parts"]] == ["Rozdział 3"]


def test_a_graduates_fragments_are_nobodys_to_do(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    _paste(client, headers, student_id)
    client.patch(
        f"/students/{student_id}", json={"status": "graduated"}, headers=headers
    )

    summary = client.get("/dashboard/summary", headers=headers).json()

    assert summary["awaiting_feedback"] == []


def test_the_dashboard_shows_nothing_of_another_promoters_students(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    other = login(client, OTHER_PROMOTOR_EMAIL, OTHER_PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    _paste(client, headers, student_id)

    summary = client.get("/dashboard/summary", headers=other).json()

    assert summary["awaiting_feedback"] == []
