"""Local models: the agent says what is installed, the admin what is offered."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from main import app
from src.mentoring.infrastructure.dependencies import get_agent_client
from src.shared.settings import settings
from tests.test_mentoring.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
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


def _names(body: dict[str, list[dict[str, str]]]) -> list[str]:
    return [m["name"] for m in body["available"]]


def _new_student(client: TestClient, headers: dict[str, str]) -> str:
    body = {
        "full_name": "Anna Nowak",
        "field_of_study": "Ekonomia",
        "thesis_type": "bachelor",
    }
    resp = client.post("/students", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


# ---------- promoter view ----------


def test_fresh_install_offers_only_the_server_default(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)

    resp = client.get("/models", headers=headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["default"] == "qwen3:30b-a3b"
    assert _names(body) == ["qwen3:30b-a3b"]
    assert body["byok"]["openai"] == "gpt-4o"


def test_promoters_see_what_the_admin_enabled(
    client: TestClient, agent: FakeAgentClient
) -> None:
    admin = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    client.patch(
        "/models/admin", json={"name": "gemma4:12b", "enabled": True}, headers=admin
    )

    promoter = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    body = client.get("/models", headers=promoter).json()

    assert _names(body) == ["gemma4:12b", "qwen3:30b-a3b"]


def test_models_is_503_when_the_agent_is_down(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    agent.unavailable = True

    assert client.get("/models", headers=headers).status_code == 503


def test_models_requires_login(client: TestClient, agent: FakeAgentClient) -> None:
    assert client.get("/models").status_code == 401


# ---------- admin ----------


def test_admin_list_shows_every_installed_model(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

    body = client.get("/models/admin", headers=headers).json()

    rows = {m["name"]: m for m in body["models"]}
    assert set(rows) == {"gemma4:12b", "llama3.1:latest", "qwen3:30b-a3b"}
    assert rows["qwen3:30b-a3b"]["is_default"] is True
    assert rows["qwen3:30b-a3b"]["enabled"] is True
    assert rows["gemma4:12b"]["enabled"] is False


def test_promoters_cannot_manage_models(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)

    assert client.get("/models/admin", headers=headers).status_code == 403
    resp = client.patch(
        "/models/admin", json={"name": "gemma4:12b", "enabled": True}, headers=headers
    )
    assert resp.status_code == 403


def test_the_default_cannot_be_disabled_until_it_has_a_successor(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

    refused = client.patch(
        "/models/admin",
        json={"name": "qwen3:30b-a3b", "enabled": False},
        headers=headers,
    )
    assert refused.status_code == 409

    moved = client.put(
        "/models/admin/default", json={"name": "gemma4:12b"}, headers=headers
    )
    assert moved.status_code == 200, moved.text
    rows = {m["name"]: m for m in moved.json()["models"]}
    assert rows["gemma4:12b"]["is_default"] is True
    assert rows["gemma4:12b"]["enabled"] is True  # made default → offered

    ok = client.patch(
        "/models/admin",
        json={"name": "qwen3:30b-a3b", "enabled": False},
        headers=headers,
    )
    assert ok.status_code == 200, ok.text

    promoter = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    body = client.get("/models", headers=promoter).json()
    assert body["default"] == "gemma4:12b"
    assert _names(body) == ["gemma4:12b"]


def test_default_can_move_twice(client: TestClient, agent: FakeAgentClient) -> None:
    headers = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    client.put("/models/admin/default", json={"name": "gemma4:12b"}, headers=headers)

    resp = client.put(
        "/models/admin/default", json={"name": "llama3.1:latest"}, headers=headers
    )

    assert resp.status_code == 200, resp.text
    defaults = [m["name"] for m in resp.json()["models"] if m["is_default"]]
    assert defaults == ["llama3.1:latest"]


def test_a_model_not_on_the_server_cannot_be_offered(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

    enable = client.patch(
        "/models/admin", json={"name": "mistral:7b", "enabled": True}, headers=headers
    )
    default = client.put(
        "/models/admin/default", json={"name": "mistral:7b"}, headers=headers
    )

    assert enable.status_code == 404
    assert default.status_code == 404


# ---------- enforcement on actions ----------


def test_an_action_on_a_disabled_model_is_refused_before_it_is_recorded(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)

    resp = client.post(
        f"/students/{student_id}/actions",
        json={"action_type": "propose_topic", "model": "llama3.1:latest"},
        headers=headers,
    )

    assert resp.status_code == 422
    assert agent.submitted == []
    history = client.get(f"/students/{student_id}/actions", headers=headers).json()
    assert history == []


def test_no_model_runs_on_the_admins_default(
    client: TestClient, agent: FakeAgentClient
) -> None:
    admin = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    client.put("/models/admin/default", json={"name": "gemma4:12b"}, headers=admin)
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)

    resp = client.post(
        f"/students/{student_id}/actions",
        json={"action_type": "propose_topic"},
        headers=headers,
    )

    assert resp.status_code == 202, resp.text
    assert agent.submitted[0]["model"] == "gemma4:12b"


def test_an_enabled_model_goes_through(
    client: TestClient, agent: FakeAgentClient
) -> None:
    admin = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    client.patch(
        "/models/admin",
        json={"name": "llama3.1:latest", "enabled": True},
        headers=admin,
    )
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)

    resp = client.post(
        f"/students/{student_id}/actions",
        json={"action_type": "propose_topic", "model": "llama3.1:latest"},
        headers=headers,
    )

    assert resp.status_code == 202, resp.text
    assert agent.submitted[0]["model"] == "llama3.1:latest"


# ---------- a server without local models (ADR 0013) ----------


@pytest.fixture
def no_local_models(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "local_models_enabled", False)


@pytest.mark.usefixtures("no_local_models")
def test_without_local_models_promoters_are_offered_none(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)

    body = client.get("/models", headers=headers).json()

    assert body["local_enabled"] is False
    assert body["available"] == []
    # Which model a provider key runs on is still the agent's to say.
    assert body["byok"]["openai"] == "gpt-4o"


@pytest.mark.usefixtures("no_local_models")
def test_without_local_models_an_action_needs_a_provider(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)

    resp = client.post(
        f"/students/{student_id}/actions",
        json={"action_type": "propose_topic"},
        headers=headers,
    )

    assert resp.status_code == 409
    assert agent.submitted == []
    history = client.get(f"/students/{student_id}/actions", headers=headers).json()
    assert history == []


@pytest.mark.usefixtures("no_local_models")
def test_without_local_models_a_provider_key_still_runs(
    client: TestClient, agent: FakeAgentClient
) -> None:
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    student_id = _new_student(client, headers)
    client.patch(
        "/settings/api-key",
        json={"api_key": "sk-ant-user-key", "provider": "claude"},
        headers=headers,
    )

    resp = client.post(
        f"/students/{student_id}/actions",
        json={"action_type": "propose_topic", "provider": "claude"},
        headers=headers,
    )

    assert resp.status_code == 202, resp.text
    assert agent.submitted[0]["byok"].provider == "claude"


@pytest.mark.usefixtures("no_local_models")
def test_the_admin_is_told_local_models_are_off(
    client: TestClient, agent: FakeAgentClient
) -> None:
    admin = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

    body = client.get("/models/admin", headers=admin).json()

    assert body["local_enabled"] is False
