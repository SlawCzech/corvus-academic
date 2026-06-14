"""Tests for the /health endpoint."""

from unittest.mock import AsyncMock, MagicMock

import httpx as _httpx
from fastapi.testclient import TestClient


def _make_get_mock(identity_result: MagicMock | Exception, agent_result: MagicMock | Exception) -> AsyncMock:
    async def _get(url: str, **_kwargs: object) -> MagicMock:
        result = identity_result if "identity" in url else agent_result
        if isinstance(result, Exception):
            raise result
        return result

    mock = AsyncMock()
    mock.get = _get
    mock.request = AsyncMock()
    return mock


def _ok_response() -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    return resp


def _bad_response(status_code: int = 500) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    return resp


# ---------- health ----------


def test_health_ok_when_all_services_up(client: TestClient) -> None:
    client.app.state.http_client = _make_get_mock(_ok_response(), _ok_response())  # type: ignore[union-attr]
    resp = client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["services"]["identity"] == "ok"
    assert body["services"]["agent"] == "ok"


def test_health_degraded_when_services_down(client: TestClient) -> None:
    client.app.state.http_client = _make_get_mock(  # type: ignore[union-attr]
        _httpx.ConnectError("refused"), _httpx.ConnectError("refused")
    )
    resp = client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["services"]["identity"] == "unavailable"
    assert body["services"]["agent"] == "unavailable"


def test_health_degraded_when_service_returns_error(client: TestClient) -> None:
    client.app.state.http_client = _make_get_mock(_ok_response(), _bad_response(500))  # type: ignore[union-attr]
    resp = client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["services"]["identity"] == "ok"
    assert body["services"]["agent"] == "degraded"


def test_health_degraded_when_service_times_out(client: TestClient) -> None:
    client.app.state.http_client = _make_get_mock(  # type: ignore[union-attr]
        _ok_response(), _httpx.TimeoutException("timed out")
    )
    resp = client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["services"]["identity"] == "ok"
    assert body["services"]["agent"] == "timeout"
