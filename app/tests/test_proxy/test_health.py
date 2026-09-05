"""Tests for the /health endpoint.

Identity is in-process after the consolidation, so `agent` is the only
downstream service still probed over the network.
"""

from unittest.mock import AsyncMock, MagicMock

import httpx as _httpx
from fastapi.testclient import TestClient


def _make_get_mock(agent_result: MagicMock | Exception) -> AsyncMock:
    async def _get(url: str, **_kwargs: object) -> MagicMock:
        if isinstance(agent_result, Exception):
            raise agent_result
        return agent_result

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


def test_health_ok_when_agent_up(client: TestClient) -> None:
    client.app.state.http_client = _make_get_mock(_ok_response())  # type: ignore[union-attr]
    resp = client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["services"]["agent"] == "ok"


def test_health_degraded_when_agent_down(client: TestClient) -> None:
    client.app.state.http_client = _make_get_mock(_httpx.ConnectError("refused"))  # type: ignore[union-attr]
    resp = client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["services"]["agent"] == "unavailable"


def test_health_degraded_when_agent_returns_error(client: TestClient) -> None:
    client.app.state.http_client = _make_get_mock(_bad_response(500))  # type: ignore[union-attr]
    resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.json()["services"]["agent"] == "degraded"


def test_health_degraded_when_agent_times_out(client: TestClient) -> None:
    client.app.state.http_client = _make_get_mock(_httpx.TimeoutException("timed out"))  # type: ignore[union-attr]
    resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.json()["services"]["agent"] == "timeout"
