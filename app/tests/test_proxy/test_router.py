"""Tests for the transitional `/analysis/*` → agent proxy.

Identity routes are no longer proxied — they are served in-process by
`src.identity.infrastructure.router`, and are covered by tests/test_identity.
"""

from unittest.mock import AsyncMock, MagicMock

import httpx as _httpx
from fastapi.testclient import TestClient


def _mock_response(content: bytes, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.content = content
    resp.status_code = status_code
    resp.headers = {"content-type": "application/json"}
    return resp


def _install_mock(
    client: TestClient, mock_response: MagicMock | Exception
) -> AsyncMock:
    """Replace app.state.http_client.request with a mock."""
    mock = AsyncMock()
    if isinstance(mock_response, Exception):
        mock.request = AsyncMock(side_effect=mock_response)
    else:
        mock.request = AsyncMock(return_value=mock_response)
    mock.get = AsyncMock(side_effect=_httpx.ConnectError("not running in tests"))
    client.app.state.http_client = mock  # type: ignore[union-attr]
    return mock


# ---------- proxy routing ----------


def test_analysis_root_proxied_to_agent(client: TestClient) -> None:
    mock = _install_mock(
        client, _mock_response(b'{"task_id":"abc-123"}', status_code=202)
    )
    resp = client.post(
        "/analysis",
        json={"evaluation_id": "e1", "text": "thesis"},
        headers={"Authorization": "Bearer tok"},
    )

    assert resp.status_code == 202
    call_kwargs = mock.request.call_args.kwargs
    assert "agent" in call_kwargs["url"]
    assert call_kwargs["url"].endswith("/analysis")


def test_analysis_subpath_proxied_to_agent(client: TestClient) -> None:
    mock = _install_mock(client, _mock_response(b'{"status":"pending"}'))
    resp = client.get("/analysis/abc-123", headers={"Authorization": "Bearer tok"})

    assert resp.status_code == 200
    assert mock.request.call_args.kwargs["url"].endswith("/analysis/abc-123")


def test_authorization_header_forwarded(client: TestClient) -> None:
    mock = _install_mock(client, _mock_response(b'{"status":"pending"}'))
    client.get("/analysis/abc-123", headers={"Authorization": "Bearer tok"})

    assert mock.request.call_args.kwargs["headers"]["authorization"] == "Bearer tok"


def test_request_id_echoed_in_response(client: TestClient) -> None:
    _install_mock(client, _mock_response(b'{"status":"pending"}'))
    resp = client.get(
        "/analysis/abc-123",
        headers={"Authorization": "Bearer tok", "x-request-id": "test-id-123"},
    )

    assert resp.headers.get("x-request-id") == "test-id-123"


def test_request_id_generated_when_absent(client: TestClient) -> None:
    _install_mock(client, _mock_response(b'{"status":"pending"}'))
    resp = client.get("/analysis/abc-123", headers={"Authorization": "Bearer tok"})

    assert "x-request-id" in resp.headers


# ---------- error handling ----------


def test_503_when_agent_down(client: TestClient) -> None:
    _install_mock(client, _httpx.ConnectError("connection refused"))
    resp = client.post(
        "/analysis",
        json={"evaluation_id": "e1", "text": "t"},
        headers={"Authorization": "Bearer tok"},
    )

    assert resp.status_code == 503


def test_504_when_upstream_times_out(client: TestClient) -> None:
    _install_mock(client, _httpx.TimeoutException("timed out"))
    resp = client.get("/analysis/abc-123", headers={"Authorization": "Bearer tok"})

    assert resp.status_code == 504
