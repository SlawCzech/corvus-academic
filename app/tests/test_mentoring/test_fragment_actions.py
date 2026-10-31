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
        json={"action_type": "review_fragment", "fragment_id": fragment_id},
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


def test_a_review_needs_a_fragment(
    client: TestClient, agent: FakeAgentClient
) -> None:
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
        json={"action_type": "generate_review"},
        headers=headers,
    )

    assert resp.status_code == 409
    assert agent.submitted == []
