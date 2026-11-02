"""A trial review reads the newest version; a final one, the accepted one."""

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from main import app
from src.mentoring.infrastructure.dependencies import get_agent_client
from tests.test_mentoring.conftest import PROMOTOR_EMAIL, PROMOTOR_PASSWORD, login
from tests.test_mentoring.fakes import FakeAgentClient, docx_bytes

_DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.fixture
def agent() -> Generator[FakeAgentClient, None, None]:
    fake = FakeAgentClient()
    app.dependency_overrides[get_agent_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_agent_client, None)


@pytest.fixture
def headers(client: TestClient) -> dict[str, str]:
    return login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)


def _student_with_two_versions(
    client: TestClient, headers: dict[str, str]
) -> tuple[str, list[str]]:
    student = client.post(
        "/students",
        json={
            "full_name": "Jan Kowalski",
            "field_of_study": "Ekonomia",
            "thesis_type": "bachelor",
        },
        headers=headers,
    ).json()
    drafts: list[str] = []
    for text in ("Wersja pierwsza.", "Wersja druga."):
        resp = client.post(
            f"/students/{student['id']}/drafts",
            files={"file": ("praca.docx", docx_bytes(text), _DOCX_TYPE)},
            headers=headers,
        )
        drafts.append(str(resp.json()["id"]))
    return str(student["id"]), drafts


def _run(
    client: TestClient,
    headers: dict[str, str],
    student_id: str,
    action_type: str,
    **body: Any,  # noqa: ANN401
) -> Any:  # noqa: ANN401
    return client.post(
        f"/students/{student_id}/actions",
        json={"action_type": action_type, **body},
        headers=headers,
    )


def test_a_trial_review_reads_the_newest_version_even_with_one_accepted(
    client: TestClient, headers: dict[str, str], agent: FakeAgentClient
) -> None:
    student_id, drafts = _student_with_two_versions(client, headers)
    client.post(f"/students/{student_id}/drafts/{drafts[0]}/accept", headers=headers)

    resp = _run(client, headers, student_id, "trial_review")

    assert resp.status_code == 202, resp.text
    assert "Wersja druga." in agent.submitted[0]["context"]["text"]
    assert agent.submitted[0]["action_type"] == "trial_review"


def test_a_final_review_reads_the_accepted_version(
    client: TestClient, headers: dict[str, str], agent: FakeAgentClient
) -> None:
    student_id, drafts = _student_with_two_versions(client, headers)
    client.post(f"/students/{student_id}/drafts/{drafts[0]}/accept", headers=headers)

    _run(client, headers, student_id, "generate_review")

    assert "Wersja pierwsza." in agent.submitted[0]["context"]["text"]


def test_a_final_review_without_an_accepted_version_reads_the_newest(
    client: TestClient, headers: dict[str, str], agent: FakeAgentClient
) -> None:
    student_id, _ = _student_with_two_versions(client, headers)

    _run(client, headers, student_id, "generate_review")

    assert "Wersja druga." in agent.submitted[0]["context"]["text"]


def test_a_final_review_passes_over_a_purged_accepted_version(
    client: TestClient, headers: dict[str, str], agent: FakeAgentClient
) -> None:
    student_id, drafts = _student_with_two_versions(client, headers)
    client.post(f"/students/{student_id}/drafts/{drafts[0]}/accept", headers=headers)
    client.delete(f"/students/{student_id}/drafts/{drafts[0]}", headers=headers)

    resp = _run(client, headers, student_id, "generate_review")

    assert resp.status_code == 202, resp.text
    assert "Wersja druga." in agent.submitted[0]["context"]["text"]


def test_both_reviews_can_pause_for_the_findings(
    client: TestClient, headers: dict[str, str], agent: FakeAgentClient
) -> None:
    student_id, _ = _student_with_two_versions(client, headers)

    _run(client, headers, student_id, "trial_review", review_findings_first=True)

    assert agent.submitted[0]["context"]["promoter_reviews_findings"] is True


def _complete_trial(
    client: TestClient,
    headers: dict[str, str],
    agent: FakeAgentClient,
    student_id: str,
    payload: dict[str, Any],
) -> str:
    action = _run(client, headers, student_id, "trial_review").json()
    agent.completes_with(payload)
    client.get(f"/students/{student_id}/actions/{action['id']}", headers=headers)
    return str(action["id"])


def test_a_mail_needs_a_finished_trial_review(
    client: TestClient, headers: dict[str, str], agent: FakeAgentClient
) -> None:
    student_id, _ = _student_with_two_versions(client, headers)
    _run(client, headers, student_id, "trial_review")

    resp = _run(client, headers, student_id, "draft_student_email")

    assert resp.status_code == 409
    assert len(agent.submitted) == 1


def test_a_mail_reads_the_newest_trial_review_and_never_the_thesis(
    client: TestClient, headers: dict[str, str], agent: FakeAgentClient
) -> None:
    student_id, _ = _student_with_two_versions(client, headers)
    finding = {"severity": "major", "section": "Wstęp", "description": "Brak hipotez"}
    _complete_trial(
        client, headers, agent, student_id, {"output": {"summary": "Starsza."}}
    )
    _complete_trial(
        client,
        headers,
        agent,
        student_id,
        {"findings": [finding], "output": {"summary": "Nowsza.", "scores": [7]}},
    )

    resp = _run(
        client, headers, student_id, "draft_student_email", detail="Termin: piątek."
    )

    assert resp.status_code == 202
    context = agent.submitted[-1]["context"]
    assert context["review_text"] == "Nowsza."
    assert context["findings"] == [finding]
    assert context["detail"] == "Termin: piątek."
    assert "text" not in context
    assert "scores" not in context


def test_a_one_off_review_takes_no_mail(
    client: TestClient, headers: dict[str, str], agent: FakeAgentClient
) -> None:
    review = client.post(
        "/reviews",
        files={"file": ("praca.docx", docx_bytes("Tekst."), _DOCX_TYPE)},
        data={
            "full_name": "Autor Pracy",
            "field_of_study": "Ekonomia",
            "thesis_type": "bachelor",
        },
        headers=headers,
    )
    assert review.status_code == 201

    resp = _run(client, headers, review.json()["id"], "draft_student_email")

    assert resp.status_code == 409
    assert agent.submitted == []
