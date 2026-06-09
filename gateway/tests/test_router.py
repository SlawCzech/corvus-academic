"""Tests for gateway proxy routing."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("IDENTITY_URL", "http://identity:8003")
os.environ.setdefault("AGENT_URL", "http://agent:8002")

import httpx as _httpx


def _mock_upstream(content: bytes, status_code: int = 200) -> MagicMock:
    """Build a mock httpx response."""
    resp = MagicMock()
    resp.content = content
    resp.status_code = status_code
    resp.headers = {"content-type": "application/json"}
    return resp


def _patch_client(mock_response: MagicMock) -> MagicMock:
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.request = AsyncMock(return_value=mock_response)
    return mock_client


# ---------- health ----------


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------- proxy routing ----------


def test_auth_login_proxied_to_identity(client: TestClient) -> None:
    mock_resp = _mock_upstream(b'{"access_token":"tok","token_type":"bearer"}')
    with patch("src.infrastructure.router.httpx.AsyncClient") as cls:
        cls.return_value = _patch_client(mock_resp)
        resp = client.post("/auth/login", json={"email": "a@b.com", "password": "x"})

    assert resp.status_code == 200
    # base_url is passed to AsyncClient constructor, url to request()
    constructor_kwargs = cls.call_args.kwargs
    assert "identity" in constructor_kwargs["base_url"]
    assert cls.return_value.request.call_args.kwargs["url"] == "/auth/login"


def test_analysis_proxied_to_agent(client: TestClient) -> None:
    mock_resp = _mock_upstream(b'{"task_id":"abc-123"}', status_code=202)
    with patch("src.infrastructure.router.httpx.AsyncClient") as cls:
        cls.return_value = _patch_client(mock_resp)
        resp = client.post(
            "/analysis",
            json={"evaluation_id": "e1", "text": "thesis"},
            headers={"Authorization": "Bearer tok"},
        )

    assert resp.status_code == 202
    constructor_kwargs = cls.call_args.kwargs
    assert "agent" in constructor_kwargs["base_url"]
    assert cls.return_value.request.call_args.kwargs["url"] == "/analysis"


def test_users_proxied_to_identity(client: TestClient) -> None:
    mock_resp = _mock_upstream(b'[{"id":"1","email":"a@b.com","role":"admin","created_at":"2026-01-01T00:00:00Z"}]')
    with patch("src.infrastructure.router.httpx.AsyncClient") as cls:
        cls.return_value = _patch_client(mock_resp)
        resp = client.get("/users", headers={"Authorization": "Bearer tok"})

    assert resp.status_code == 200
    assert "identity" in cls.call_args.kwargs["base_url"]


# ---------- error handling ----------


def test_503_when_identity_down(client: TestClient) -> None:
    with patch("src.infrastructure.router.httpx.AsyncClient") as cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.request = AsyncMock(
            side_effect=_httpx.ConnectError("connection refused")
        )
        cls.return_value = mock_client
        resp = client.post("/auth/login", json={"email": "a@b.com", "password": "x"})

    assert resp.status_code == 503


def test_503_when_agent_down(client: TestClient) -> None:
    with patch("src.infrastructure.router.httpx.AsyncClient") as cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.request = AsyncMock(
            side_effect=_httpx.ConnectError("connection refused")
        )
        cls.return_value = mock_client
        resp = client.post(
            "/analysis",
            json={"evaluation_id": "e1", "text": "t"},
            headers={"Authorization": "Bearer tok"},
        )

    assert resp.status_code == 503
