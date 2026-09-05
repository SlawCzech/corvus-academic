"""Integration tests for identity HTTP endpoints using TestClient."""

import os
import uuid
from typing import Any

from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-key-that-is-long-enough-32ch")
os.environ.setdefault("FERNET_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")

from tests.test_identity.conftest import (  # noqa: E402
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    PROMOTOR_EMAIL,
    PROMOTOR_PASSWORD,
)


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return str(resp.json()["access_token"])


# ---------- login ----------
# /health is covered in tests/test_proxy/test_health.py — post-consolidation it
# reports downstream service status rather than a flat "ok".


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
        json={"email": "new@example.com", "password": "pass123", "role": "promotor"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body: dict[str, Any] = resp.json()
    assert body["email"] == "new@example.com"
    assert body["role"] == "promotor"


def test_create_user_duplicate_email(client: TestClient) -> None:
    token = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    client.post(
        "/users",
        json={"email": "dup@example.com", "password": "pass", "role": "promotor"},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = client.post(
        "/users",
        json={"email": "dup@example.com", "password": "pass2", "role": "promotor"},
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
        json={
            "email": "todelete@example.com",
            "password": "pass",
            "role": "promotor",
        },
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


# ---------- api-key ----------


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


# ---------- invalid token ----------


def test_invalid_token_rejected(client: TestClient) -> None:
    headers = {"Authorization": "Bearer not.a.valid.token"}
    resp = client.get("/users/me", headers=headers)
    assert resp.status_code == 401


# ---------- removed endpoints ----------


def test_internal_endpoints_are_gone(client: TestClient) -> None:
    """`/internal/*` was deleted in the consolidation — see router.py note.

    These endpoints relied on gateway not proxying them; on the merged public
    port they would have been an unauthenticated user lookup and a token oracle.
    """
    introspect = client.post("/internal/token/introspect", json={"token": "x"})
    assert introspect.status_code == 404
    assert client.get(f"/internal/users/{uuid.uuid4()}").status_code == 404
