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
