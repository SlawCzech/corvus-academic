"""Integration tests for gateway HTTP endpoints using TestClient."""

import os
import uuid
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-key-that-is-long-enough-32ch")
os.environ.setdefault("FERNET_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")

from tests.conftest import (  # noqa: E402
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    PROMOTOR_EMAIL,
    PROMOTOR_PASSWORD,
)


def _login(client: TestClient, email: str, password: str) -> str:
    """POST /auth/login and return the access token."""
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return str(resp.json()["access_token"])


@pytest.fixture
def mock_celery() -> Generator[MagicMock, None, None]:
    fake_task_id = str(uuid.uuid4())
    with patch(
        "src.infrastructure.router.celery_client.send_analysis_task",
        return_value=fake_task_id,
    ) as mock_send, patch(
        "src.infrastructure.router.celery_client.get_task_result",
        return_value={"status": "SUCCESS", "result": {"score": 85}},
    ) as mock_get:
        mock = MagicMock()
        mock.task_id = fake_task_id
        mock.send = mock_send
        mock.get = mock_get
        yield mock


# ---------- health ----------


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------- login ----------


def test_login_admin_success(client: TestClient) -> None:
    resp = client.post(
        "/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert resp.status_code == 200
    body: dict[str, Any] = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"  # noqa: S105


def test_login_promotor_success(client: TestClient) -> None:
    resp = client.post(
        "/auth/login",
        json={"email": PROMOTOR_EMAIL, "password": PROMOTOR_PASSWORD},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_wrong_password(client: TestClient) -> None:
    resp = client.post(
        "/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"}
    )
    assert resp.status_code == 401


def test_login_unknown_email(client: TestClient) -> None:
    resp = client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "any"}
    )
    assert resp.status_code == 401


# ---------- protected endpoints without token ----------


def test_submit_analysis_requires_auth(client: TestClient) -> None:
    resp = client.post("/analysis", json={"evaluation_id": "x", "text": "t"})
    assert resp.status_code in (401, 403)


def test_get_analysis_status_requires_auth(client: TestClient) -> None:
    resp = client.get(f"/analysis/{uuid.uuid4()}")
    assert resp.status_code in (401, 403)


def test_invalid_token_rejected(client: TestClient) -> None:
    headers = {"Authorization": "Bearer not.a.valid.token"}
    resp = client.post(
        "/analysis",
        json={"evaluation_id": "x", "text": "t"},
        headers=headers,
    )
    assert resp.status_code == 401


# ---------- /users/me ----------


def test_get_me(client: TestClient) -> None:
    token = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    resp = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body: dict[str, Any] = resp.json()
    assert body["email"] == ADMIN_EMAIL
    assert body["role"] == "admin"


# ---------- /users CRUD ----------


def test_list_users_admin(client: TestClient) -> None:
    token = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    resp = client.get("/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    emails = [u["email"] for u in resp.json()]
    assert ADMIN_EMAIL in emails
    assert PROMOTOR_EMAIL in emails


def test_list_users_forbidden_for_promotor(client: TestClient) -> None:
    token = _login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    resp = client.get("/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_create_user_admin(client: TestClient) -> None:
    token = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    resp = client.post(
        "/users",
        json={"email": "new@corvus.local", "password": "pass123", "role": "promotor"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body: dict[str, Any] = resp.json()
    assert body["email"] == "new@corvus.local"
    assert body["role"] == "promotor"


def test_create_user_duplicate_email(client: TestClient) -> None:
    token = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    client.post(
        "/users",
        json={"email": "dup@corvus.local", "password": "pass", "role": "promotor"},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = client.post(
        "/users",
        json={"email": "dup@corvus.local", "password": "pass2", "role": "promotor"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


def test_create_user_forbidden_for_promotor(client: TestClient) -> None:
    token = _login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    resp = client.post(
        "/users",
        json={"email": "x@x.com", "password": "p", "role": "promotor"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_delete_user_admin(client: TestClient) -> None:
    token = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    create_resp = client.post(
        "/users",
        json={"email": "todelete@corvus.local", "password": "pass", "role": "promotor"},
        headers={"Authorization": f"Bearer {token}"},
    )
    user_id = create_resp.json()["id"]
    resp = client.delete(
        f"/users/{user_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 204


def test_change_password(client: TestClient) -> None:
    token = _login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    resp = client.patch(
        "/users/me/password",
        json={"new_password": "new-secure-password"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204
    new_token = _login(client, PROMOTOR_EMAIL, "new-secure-password")
    assert len(new_token) > 0


# ---------- submit analysis ----------


def test_submit_analysis_success(client: TestClient, mock_celery: MagicMock) -> None:
    token = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    resp = client.post(
        "/analysis",
        json={"evaluation_id": str(uuid.uuid4()), "text": "thesis content"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 202
    body: dict[str, Any] = resp.json()
    assert "task_id" in body
    assert body["task_id"] == mock_celery.task_id
    mock_celery.send.assert_called_once()


def test_submit_analysis_as_promotor(
    client: TestClient, mock_celery: MagicMock
) -> None:
    token = _login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    resp = client.post(
        "/analysis",
        json={"evaluation_id": "e1", "text": "text"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 202


# ---------- analysis history ----------


def test_list_analyses_empty(client: TestClient) -> None:
    token = _login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    resp = client.get("/analysis", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_analyses_after_submit(
    client: TestClient, mock_celery: MagicMock
) -> None:
    token = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    client.post(
        "/analysis",
        json={"evaluation_id": "e1", "text": "t"},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = client.get("/analysis", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ---------- task status ----------


def test_get_task_status_admin_sees_any(
    client: TestClient, mock_celery: MagicMock
) -> None:
    token = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    resp = client.get(
        f"/analysis/{mock_celery.task_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body: dict[str, Any] = resp.json()
    assert body["status"] == "SUCCESS"
    assert body["result"] == {"score": 85}


def test_get_task_status_owner_can_see(
    client: TestClient, mock_celery: MagicMock
) -> None:
    token = _login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    submit = client.post(
        "/analysis",
        json={"evaluation_id": "e1", "text": "t"},
        headers={"Authorization": f"Bearer {token}"},
    )
    task_id = submit.json()["task_id"]
    resp = client.get(
        f"/analysis/{task_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


def test_get_task_status_non_owner_gets_404(
    client: TestClient, mock_celery: MagicMock
) -> None:
    admin_token = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    client.post(
        "/analysis",
        json={"evaluation_id": "e1", "text": "t"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    promotor_token = _login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    resp = client.get(
        f"/analysis/{mock_celery.task_id}",
        headers={"Authorization": f"Bearer {promotor_token}"},
    )
    assert resp.status_code == 404


def test_get_task_status_pending(client: TestClient) -> None:
    token = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    with patch(
        "src.infrastructure.router.celery_client.get_task_result",
        return_value={"status": "PENDING", "result": None},
    ):
        resp = client.get(
            f"/analysis/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "PENDING"
    assert resp.json()["result"] is None


# ---------- admin login-events ----------


def test_admin_login_events(client: TestClient) -> None:
    token = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    resp = client.get(
        "/admin/login-events",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) >= 1
    assert any(e["email"] == ADMIN_EMAIL and e["success"] for e in events)


def test_admin_login_events_forbidden_for_promotor(client: TestClient) -> None:
    token = _login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    resp = client.get(
        "/admin/login-events",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


# ---------- PATCH /settings/api-key ----------


def test_set_api_key_admin_success(client: TestClient) -> None:
    token = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    resp = client.patch(
        "/settings/api-key",
        json={"api_key": "sk-ant-test-key", "provider": "claude"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"configured": True}


def test_set_api_key_promotor_forbidden(client: TestClient) -> None:
    token = _login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    resp = client.patch(
        "/settings/api-key",
        json={"api_key": "sk-openai-test", "provider": "openai"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_set_api_key_requires_auth(client: TestClient) -> None:
    resp = client.patch(
        "/settings/api-key",
        json={"api_key": "sk-test", "provider": "claude"},
    )
    assert resp.status_code in (401, 403)


def test_response_never_contains_plain_key(client: TestClient) -> None:
    plain_key = "sk-ant-super-secret-value"
    token = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    resp = client.patch(
        "/settings/api-key",
        json={"api_key": plain_key, "provider": "claude"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert plain_key not in resp.text


# ---------- GET /settings/api-key/status ----------


def test_get_status_not_configured(client: TestClient) -> None:
    token = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    resp = client.get(
        "/settings/api-key/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"configured": False}


def test_get_status_configured_after_set(client: TestClient) -> None:
    token = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    client.patch(
        "/settings/api-key",
        json={"api_key": "sk-ant-key", "provider": "claude"},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = client.get(
        "/settings/api-key/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"configured": True}


def test_get_status_requires_auth(client: TestClient) -> None:
    resp = client.get("/settings/api-key/status")
    assert resp.status_code in (401, 403)
