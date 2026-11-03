"""Integration tests for identity HTTP endpoints using TestClient."""

import os
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx import Response

os.environ.setdefault("JWT_SECRET", "test-secret-key-that-is-long-enough-32ch")
os.environ.setdefault("FERNET_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")

from src.identity.application.key_check import KeyVerdict  # noqa: E402
from src.shared.settings import settings  # noqa: E402
from tests.conftest import InMemoryTokenStore  # noqa: E402
from tests.test_identity.conftest import (  # noqa: E402
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    PROMOTOR_EMAIL,
    PROMOTOR_PASSWORD,
    FakeKeyChecker,
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
    resp = client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"})
    assert resp.status_code == 401


def test_login_password_over_bcrypt_limit_is_401(client: TestClient) -> None:
    resp = client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": "ż" * 37})
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


# ---------- refresh ----------


def _refresh_with(client: TestClient, token: str) -> Response:
    client.cookies.clear()
    return client.post("/auth/refresh", headers={"Cookie": f"refresh_token={token}"})


def _login_refresh_token(client: TestClient) -> str:
    resp = client.post(
        "/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    return resp.cookies["refresh_token"]


def test_refresh_replaces_both_tokens(client: TestClient) -> None:
    old = _login_refresh_token(client)

    resp = _refresh_with(client, old)

    assert resp.status_code == 200
    assert resp.cookies["refresh_token"] != old
    me = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {resp.json()['access_token']}"},
    )
    assert me.status_code == 200


def test_refresh_retires_the_token_it_replaced(
    client: TestClient, token_store: InMemoryTokenStore
) -> None:
    old = _login_refresh_token(client)
    assert _refresh_with(client, old).status_code == 200

    token_store.end_grace()

    resp = _refresh_with(client, old)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Refresh token revoked"


def test_refresh_accepts_a_second_use_within_the_grace_period(
    client: TestClient,
) -> None:
    # Two tabs renewing at once: the loser must not be logged out for it.
    old = _login_refresh_token(client)

    assert _refresh_with(client, old).status_code == 200
    assert _refresh_with(client, old).status_code == 200


def test_refresh_chain_keeps_working(
    client: TestClient, token_store: InMemoryTokenStore
) -> None:
    token = _login_refresh_token(client)
    for _ in range(3):
        resp = _refresh_with(client, token)
        assert resp.status_code == 200
        token = resp.cookies["refresh_token"]
        token_store.end_grace()


def test_refresh_without_a_cookie_is_refused(client: TestClient) -> None:
    client.cookies.clear()
    assert client.post("/auth/refresh").status_code == 401


# ---------- logout ----------


def test_logout_revokes_the_access_token_in_use(
    client: TestClient, token_store: InMemoryTokenStore
) -> None:
    token = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    auth = {"Authorization": f"Bearer {token}"}

    assert client.post("/auth/logout", headers=auth).status_code == 204

    resp = client.get("/users/me", headers=auth)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Token revoked"
    # Revoked for as long as the token would otherwise still be accepted.
    (ttl,) = token_store.revoked.values()
    assert 0 < ttl <= settings.access_token_expire_minutes * 60 + 1


def test_logout_leaves_other_sessions_alone(client: TestClient) -> None:
    first = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    second = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

    client.post("/auth/logout", headers={"Authorization": f"Bearer {first}"})

    resp = client.get("/users/me", headers={"Authorization": f"Bearer {second}"})
    assert resp.status_code == 200


def test_logout_without_a_token_still_succeeds(client: TestClient) -> None:
    assert client.post("/auth/logout").status_code == 204
    resp = client.post("/auth/logout", headers={"Authorization": "Bearer not.a.token"})
    assert resp.status_code == 204


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


@pytest.mark.parametrize("email", ["ktos@uczelnia.local", "bez-malpy"])
def test_create_user_invalid_email_is_422(client: TestClient, email: str) -> None:
    token = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    auth = {"Authorization": f"Bearer {token}"}

    resp = client.post(
        "/users",
        json={"email": email, "password": "pass123", "role": "promotor"},
        headers=auth,
    )

    assert resp.status_code == 422
    # The admin form shows `detail` as-is, so it stays a string.
    assert resp.json()["detail"].startswith("Invalid email")
    emails = [u["email"] for u in client.get("/users", headers=auth).json()]
    assert email not in emails


def test_create_user_password_over_bcrypt_limit_is_422(client: TestClient) -> None:
    token = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    resp = client.post(
        "/users",
        json={"email": "dlugie@example.com", "password": "x" * 73, "role": "promotor"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


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
        json={
            "current_password": PROMOTOR_PASSWORD,
            "new_password": "new-secure-password",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    new_token = _login(client, PROMOTOR_EMAIL, "new-secure-password")
    assert len(new_token) > 0


def test_change_password_ends_every_other_session(client: TestClient) -> None:
    other_browser = client.post(
        "/auth/login", json={"email": PROMOTOR_EMAIL, "password": PROMOTOR_PASSWORD}
    ).cookies["refresh_token"]
    token = _login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    resp = client.patch(
        "/users/me/password",
        json={
            "current_password": PROMOTOR_PASSWORD,
            "new_password": "new-secure-password",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    def me(access: str) -> int:
        headers = {"Authorization": f"Bearer {access}"}
        return client.get("/users/me", headers=headers).status_code

    assert me(token) == 401
    assert _refresh_with(client, other_browser).status_code == 401
    # The browser that made the change carries on with the pair it got back.
    assert me(resp.json()["access_token"]) == 200
    assert _refresh_with(client, resp.cookies["refresh_token"]).status_code == 200


@pytest.mark.parametrize("current", ["wrong-password", "ż" * 37])
def test_change_password_with_wrong_current_is_403(
    client: TestClient, current: str
) -> None:
    token = _login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    resp = client.patch(
        "/users/me/password",
        json={"current_password": current, "new_password": "new-secure-password"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert isinstance(resp.json()["detail"], str)
    assert len(_login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)) > 0


def test_change_password_without_current_is_422(client: TestClient) -> None:
    token = _login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    resp = client.patch(
        "/users/me/password",
        json={"new_password": "new-secure-password"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert len(_login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)) > 0


def test_change_password_over_bcrypt_limit_is_422(client: TestClient) -> None:
    token = _login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    resp = client.patch(
        "/users/me/password",
        # 37 characters, 74 bytes: the limit counts bytes.
        json={"current_password": PROMOTOR_PASSWORD, "new_password": "ż" * 37},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert isinstance(resp.json()["detail"], str)
    assert len(_login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)) > 0


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


# ---------- api-key (BYOK) ----------


def test_promotor_can_set_their_own_key(client: TestClient) -> None:
    """The key is the promoter's own and is billed to their account."""
    token = _login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    resp = client.patch(
        "/settings/api-key",
        json={"api_key": "sk-openai-test-key", "provider": "openai"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "configured": True,
        "providers": ["openai"],
        "verified": True,
    }


def test_set_api_key_promotor_success(client: TestClient) -> None:
    token = _login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    resp = client.patch(
        "/settings/api-key",
        json={"api_key": "sk-ant-test-key", "provider": "claude"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "configured": True,
        "providers": ["claude"],
        "verified": True,
    }


def test_a_second_providers_key_is_kept_next_to_the_first(client: TestClient) -> None:
    """One key per provider: saving OpenAI must not overwrite Claude."""
    token = _login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    client.patch(
        "/settings/api-key",
        json={"api_key": "sk-ant-test-key", "provider": "claude"},
        headers=headers,
    )

    resp = client.patch(
        "/settings/api-key",
        json={"api_key": "sk-openai-test-key", "provider": "openai"},
        headers=headers,
    )

    assert resp.status_code == 200
    assert resp.json()["providers"] == ["claude", "openai"]
    status_now = client.get("/settings/api-key/status", headers=headers).json()
    assert status_now == {"configured": True, "providers": ["claude", "openai"]}


def test_key_is_checked_with_the_provider_before_it_is_stored(
    client: TestClient, key_checker: FakeKeyChecker
) -> None:
    token = _login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    client.patch(
        "/settings/api-key",
        json={"api_key": "sk-ant-test-key", "provider": "claude"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert key_checker.checked == [("claude", "sk-ant-test-key")]


def test_a_key_the_provider_rejects_is_not_stored(
    client: TestClient, key_checker: FakeKeyChecker
) -> None:
    """A typo is caught at the save button, not on the next AI action."""
    token = _login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    client.patch(
        "/settings/api-key",
        json={"api_key": "sk-ant-working-key", "provider": "claude"},
        headers=headers,
    )
    key_checker.verdict = KeyVerdict.REJECTED

    resp = client.patch(
        "/settings/api-key",
        json={"api_key": "sk-openai-typo", "provider": "openai"},
        headers=headers,
    )

    assert resp.status_code == 422
    assert resp.json() == {
        "detail": "The provider rejected this key",
        "provider_message": None,
    }
    # The key that worked is still the one in use.
    status_now = client.get("/settings/api-key/status", headers=headers).json()
    assert status_now == {"configured": True, "providers": ["claude"]}


def test_a_rejection_carries_what_the_provider_said(
    client: TestClient, key_checker: FakeKeyChecker
) -> None:
    """ "Rejected" alone sends the promoter looking for a typo that is not there."""
    key_checker.verdict = KeyVerdict.REJECTED
    key_checker.provider_message = "This API key is not scoped to a workspace"
    token = _login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.patch(
        "/settings/api-key",
        json={"api_key": "sk-ant-test-key", "provider": "claude"},
        headers=headers,
    )

    assert resp.status_code == 422
    assert resp.json()["provider_message"] == (
        "This API key is not scoped to a workspace"
    )
    status_now = client.get("/settings/api-key/status", headers=headers).json()
    assert status_now == {"configured": False, "providers": []}


def test_a_key_that_could_not_be_checked_is_stored_unverified(
    client: TestClient, key_checker: FakeKeyChecker
) -> None:
    """Offline is not a verdict on the key: save it, and say it is unchecked."""
    key_checker.verdict = KeyVerdict.UNCHECKED
    token = _login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)

    resp = client.patch(
        "/settings/api-key",
        json={"api_key": "sk-ant-test-key", "provider": "claude"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    assert resp.json() == {
        "configured": True,
        "providers": ["claude"],
        "verified": False,
    }


def test_admin_has_no_api_key_settings(client: TestClient) -> None:
    """An admin runs no AI actions, so there is nothing for a key to pay for."""
    headers = {"Authorization": f"Bearer {_login(client, ADMIN_EMAIL, ADMIN_PASSWORD)}"}
    resp = client.patch(
        "/settings/api-key",
        json={"api_key": "sk-ant-test-key", "provider": "claude"},
        headers=headers,
    )
    assert resp.status_code == 403
    assert client.get("/settings/api-key/status", headers=headers).status_code == 403


def test_unsupported_provider_is_rejected(client: TestClient) -> None:
    token = _login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    resp = client.patch(
        "/settings/api-key",
        json={"api_key": "sk-something", "provider": "deepmind"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_response_never_contains_plain_key(client: TestClient) -> None:
    plain_key = "sk-ant-super-secret-value"
    token = _login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    resp = client.patch(
        "/settings/api-key",
        json={"api_key": plain_key, "provider": "claude"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert plain_key not in resp.text


def test_get_status_not_configured(client: TestClient) -> None:
    token = _login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    resp = client.get(
        "/settings/api-key/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"configured": False, "providers": []}


def test_status_reports_the_provider(client: TestClient) -> None:
    token = _login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
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
    assert resp.json() == {"configured": True, "providers": ["claude"]}


def test_key_can_be_removed(client: TestClient) -> None:
    """Removing the key falls back to the self-hosted model, not to nothing."""
    token = _login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    client.patch(
        "/settings/api-key",
        json={"api_key": "sk-openai-key", "provider": "openai"},
        headers=headers,
    )

    resp = client.delete("/settings/api-key/openai", headers=headers)

    assert resp.status_code == 200
    assert resp.json() == {"configured": False, "providers": []}
    status = client.get("/settings/api-key/status", headers=headers).json()
    assert status["configured"] is False


def test_removing_one_key_leaves_the_other(client: TestClient) -> None:
    token = _login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    for provider, key in (("claude", "sk-ant-key"), ("openai", "sk-openai-key")):
        client.patch(
            "/settings/api-key",
            json={"api_key": key, "provider": provider},
            headers=headers,
        )

    resp = client.delete("/settings/api-key/openai", headers=headers)

    assert resp.json() == {"configured": True, "providers": ["claude"]}
    # Removing it again is not an error.
    again = client.delete("/settings/api-key/openai", headers=headers)
    assert again.status_code == 200


def test_removing_a_key_for_an_unknown_provider_is_404(client: TestClient) -> None:
    token = _login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    resp = client.delete(
        "/settings/api-key/deepmind", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404


def test_status_requires_auth(client: TestClient) -> None:
    assert client.get("/settings/api-key/status").status_code == 401


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
