"""Tests for the /health endpoint.

Identity is in-process after the consolidation, so `agent` is the only
downstream service still probed over the network.
"""

import asyncio
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


# ---------- the worker, reported through agent ----------


def _by_path(routes: dict[str, MagicMock | Exception]) -> AsyncMock:
    """A client answering per URL suffix; the longest suffix wins."""

    async def _get(url: str, **_kwargs: object) -> MagicMock:
        path = max((p for p in routes if url.endswith(p)), key=len)
        result = routes[path]
        if isinstance(result, Exception):
            raise result
        return result

    mock = AsyncMock()
    mock.get = _get
    return mock


def test_health_reports_the_worker_as_ok(client: TestClient) -> None:
    client.app.state.http_client = _by_path(  # type: ignore[union-attr]
        {"/health": _ok_response(), "/health/worker": _ok_response()}
    )
    body = client.get("/health").json()

    assert body == {"status": "ok", "services": {"agent": "ok", "worker": "ok"}}


def test_dead_worker_is_degraded_but_still_http_200(client: TestClient) -> None:
    """`deploy.sh` runs `curl -f`: a 503 here would roll the deploy back."""
    client.app.state.http_client = _by_path(  # type: ignore[union-attr]
        {"/health": _ok_response(), "/health/worker": _bad_response(503)}
    )
    resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.json() == {
        "status": "degraded",
        "services": {"agent": "ok", "worker": "unavailable"},
    }


def test_worker_probe_timing_out_does_not_cost_the_agent_probe(
    client: TestClient,
) -> None:
    client.app.state.http_client = _by_path(  # type: ignore[union-attr]
        {
            "/health": _ok_response(),
            "/health/worker": _httpx.TimeoutException("timed out"),
        }
    )
    resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.json()["services"] == {"agent": "ok", "worker": "timeout"}


def test_probes_run_side_by_side(client: TestClient) -> None:
    """In sequence, two 3 s timeouts would outlast the 5 s container healthcheck."""
    running = 0
    peak = 0

    async def _get(url: str, **_kwargs: object) -> MagicMock:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.01)
        running -= 1
        return _ok_response()

    mock = AsyncMock()
    mock.get = _get
    client.app.state.http_client = mock  # type: ignore[union-attr]
    client.get("/health")

    assert peak == 2
