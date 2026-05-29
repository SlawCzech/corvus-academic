"""Integration tests for gateway HTTP endpoints using TestClient."""

import os
import uuid
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-key-that-is-long-enough-32ch")

# ---------- helpers ----------

_ADMIN_EMAIL = "admin@corvus.local"
_ADMIN_PASSWORD = "admin-secret"
_PROMOTOR_EMAIL = "promotor@corvus.local"
_PROMOTOR_PASSWORD = "promotor-secret"


def _login(client: TestClient, email: str, password: str) -> str:
    """POST /auth/login and return the access token."""
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return str(resp.json()["access_token"])


# ---------- fixtures ----------


@pytest.fixture
def mock_celery() -> Generator[MagicMock, None, None]:
    """Patch the celery_client module used by the router."""
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
        "/auth/login", json={"email": _ADMIN_EMAIL, "password": _ADMIN_PASSWORD}
    )
    assert resp.status_code == 200
    body: dict[str, Any] = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"  # noqa: S105


def test_login_promotor_success(client: TestClient) -> None:
    resp = client.post(
        "/auth/login",
        json={"email": _PROMOTOR_EMAIL, "password": _PROMOTOR_PASSWORD},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_wrong_password(client: TestClient) -> None:
    resp = client.post(
        "/auth/login", json={"email": _ADMIN_EMAIL, "password": "wrong"}
    )
    assert resp.status_code == 401


def test_login_unknown_email(client: TestClient) -> None:
    resp = client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "any"}
    )
    assert resp.status_code == 401


# ---------- protected endpoints without token ----------


def test_submit_analysis_requires_auth(client: TestClient) -> None:
    resp = client.post(
        "/analysis", json={"evaluation_id": "x", "text": "t", "guidelines": "g"}
    )
    assert resp.status_code in (401, 403)


def test_get_analysis_status_requires_auth(client: TestClient) -> None:
    resp = client.get(f"/analysis/{uuid.uuid4()}")
    assert resp.status_code in (401, 403)


def test_invalid_token_rejected(client: TestClient) -> None:
    headers = {"Authorization": "Bearer not.a.valid.token"}
    resp = client.post(
        "/analysis",
        json={"evaluation_id": "x", "text": "t", "guidelines": "g"},
        headers=headers,
    )
    assert resp.status_code == 401


# ---------- submit analysis ----------


def test_submit_analysis_success(client: TestClient, mock_celery: MagicMock) -> None:
    token = _login(client, _ADMIN_EMAIL, _ADMIN_PASSWORD)
    resp = client.post(
        "/analysis",
        json={
            "evaluation_id": str(uuid.uuid4()),
            "text": "thesis content",
            "guidelines": "university guidelines",
            "metadata": {"author": "Jan Kowalski"},
        },
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
    token = _login(client, _PROMOTOR_EMAIL, _PROMOTOR_PASSWORD)
    resp = client.post(
        "/analysis",
        json={"evaluation_id": "e1", "text": "text", "guidelines": "g"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 202


# ---------- task status ----------


def test_get_task_status_success(client: TestClient, mock_celery: MagicMock) -> None:
    token = _login(client, _ADMIN_EMAIL, _ADMIN_PASSWORD)
    resp = client.get(
        f"/analysis/{mock_celery.task_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body: dict[str, Any] = resp.json()
    assert body["status"] == "SUCCESS"
    assert body["result"] == {"score": 85}
    mock_celery.get.assert_called_once_with(mock_celery.task_id)


def test_get_task_status_pending(client: TestClient) -> None:
    token = _login(client, _ADMIN_EMAIL, _ADMIN_PASSWORD)
    with patch(
        "src.infrastructure.router.celery_client.get_task_result",
        return_value={"status": "PENDING", "result": None},
    ):
        resp = client.get(
            f"/analysis/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    body: dict[str, Any] = resp.json()
    assert body["status"] == "PENDING"
    assert body["result"] is None
