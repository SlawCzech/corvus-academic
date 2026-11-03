"""The model catalog: which model each provider's key runs on (ADR 0022)."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from main import app
from src.mentoring.infrastructure.dependencies import get_agent_client
from tests.test_mentoring.conftest import (
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


def test_promoters_see_the_model_each_provider_runs_on(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)

    resp = client.get("/models", headers=headers)

    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "byok": {"claude": "claude-sonnet-5-5", "openai": "gpt-6.1-sol"}
    }


def test_the_catalog_needs_a_login(client: TestClient, agent: FakeAgentClient) -> None:
    assert client.get("/models").status_code == 401


def test_the_catalog_is_503_without_the_agent(
    client: TestClient, agent: FakeAgentClient
) -> None:
    agent.unavailable = True
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)

    assert client.get("/models", headers=headers).status_code == 503


def test_the_admin_pages_for_local_models_are_gone(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)

    assert client.get("/models/admin", headers=headers).status_code in (404, 405)
