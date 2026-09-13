"""Integration tests for the access-request endpoints.

There is no self-signup: a visitor leaves an email, an admin sees it and
decides whether to create a real account through the existing
user-management endpoint. These tests cover that queue, not account
creation.
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from main import app
from src.identity.infrastructure.limiter import access_request_rate_limit
from tests.test_identity.conftest import ADMIN_EMAIL, ADMIN_PASSWORD


async def _noop_rate_limit() -> None:
    """No-op — the real limiter needs Redis, which these tests don't run."""


@pytest.fixture(autouse=True)
def _no_rate_limit() -> Generator[None, None, None]:
    app.dependency_overrides[access_request_rate_limit] = _noop_rate_limit
    yield
    app.dependency_overrides.pop(access_request_rate_limit, None)


def login(client: TestClient, email: str, password: str) -> dict[str, str]:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token: str = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_submitting_a_request_needs_no_auth(client: TestClient) -> None:
    resp = client.post("/access-requests", json={"email": "kandydat@uczelnia.edu.pl"})

    assert resp.status_code == 201, resp.text
    assert resp.json()["email"] == "kandydat@uczelnia.edu.pl"


def test_rejects_an_invalid_email(client: TestClient) -> None:
    resp = client.post("/access-requests", json={"email": "not-an-email"})

    assert resp.status_code == 422


def test_admin_sees_pending_requests_newest_first(client: TestClient) -> None:
    client.post("/access-requests", json={"email": "first@uczelnia.edu.pl"})
    client.post("/access-requests", json={"email": "second@uczelnia.edu.pl"})
    headers = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

    resp = client.get("/access-requests", headers=headers)

    assert resp.status_code == 200, resp.text
    emails = [r["email"] for r in resp.json()]
    assert emails == ["second@uczelnia.edu.pl", "first@uczelnia.edu.pl"]


def test_listing_requires_admin(client: TestClient) -> None:
    resp = client.get("/access-requests")
    assert resp.status_code == 401


def test_admin_can_dismiss_a_request(client: TestClient) -> None:
    client.post("/access-requests", json={"email": "kandydat@uczelnia.edu.pl"})
    headers = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    request_id = client.get("/access-requests", headers=headers).json()[0]["id"]

    resp = client.delete(f"/access-requests/{request_id}", headers=headers)

    assert resp.status_code == 204
    assert client.get("/access-requests", headers=headers).json() == []


def test_dismissing_an_unknown_request_is_not_found(client: TestClient) -> None:
    headers = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    resp = client.delete(
        "/access-requests/00000000-0000-0000-0000-000000000099", headers=headers
    )
    assert resp.status_code == 404
