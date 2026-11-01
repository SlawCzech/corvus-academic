"""Tests for the HTTP access log."""

from collections.abc import Generator
from unittest.mock import AsyncMock

import pytest
import structlog
from fastapi import FastAPI
from fastapi.testclient import TestClient
from structlog.typing import EventDict

from src.shared.middleware import access_log_middleware


def _app() -> FastAPI:
    app = FastAPI()
    app.middleware("http")(access_log_middleware)

    @app.get("/thing")
    async def thing() -> dict[str, str]:
        return {"ok": "yes"}

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("boom")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


@pytest.fixture
def logs() -> Generator[list[EventDict]]:
    with structlog.testing.capture_logs() as captured:
        yield captured


def _requests(logs: list[EventDict]) -> list[EventDict]:
    return [e for e in logs if e["event"] == "http_request"]


def test_logs_method_path_status_and_time(logs: list[EventDict]) -> None:
    TestClient(_app()).get("/thing")

    [entry] = _requests(logs)
    assert entry["method"] == "GET"
    assert entry["path"] == "/thing"
    assert entry["status"] == 200
    assert entry["duration_ms"] >= 0


def test_logs_nothing_else(logs: list[EventDict]) -> None:
    """No query string, headers or body: tokens and thesis text travel there."""
    TestClient(_app()).get(
        "/thing?token=secret-query",
        headers={"authorization": "Bearer secret-header"},
    )

    [entry] = _requests(logs)
    assert set(entry) == {
        "event",
        "log_level",
        "method",
        "path",
        "status",
        "duration_ms",
    }
    assert "secret" not in str(entry)


def test_skips_health(logs: list[EventDict]) -> None:
    TestClient(_app()).get("/health")

    assert _requests(logs) == []


def test_logs_a_404(logs: list[EventDict]) -> None:
    TestClient(_app()).get("/nowhere")

    assert _requests(logs)[0]["status"] == 404


def test_logs_a_handler_that_raised_as_500(logs: list[EventDict]) -> None:
    resp = TestClient(_app(), raise_server_exceptions=False).get("/boom")

    assert resp.status_code == 500
    assert _requests(logs)[0]["status"] == 500


def test_wired_into_the_app(client: TestClient, logs: list[EventDict]) -> None:
    client.get("/nowhere?x=1")
    client.app.state.http_client = AsyncMock()  # type: ignore[union-attr]
    client.get("/health")

    assert [e["path"] for e in _requests(logs)] == ["/nowhere"]
