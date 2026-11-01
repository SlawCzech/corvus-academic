"""Tests for `GET /health/worker` and the ping behind it."""

import asyncio
import os
import threading
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from kombu.exceptions import OperationalError

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/thesis_reviewer"
)
os.environ.setdefault("JWT_SECRET", "test-secret-key-that-is-long-enough-32ch")

from main import app  # noqa: E402
from src.infrastructure import worker_health  # noqa: E402


@pytest.fixture(autouse=True)
def no_ping_left_over() -> Generator[None]:
    worker_health._in_flight = None  # pyright: ignore[reportPrivateUsage]
    yield
    worker_health._in_flight = None  # pyright: ignore[reportPrivateUsage]


def _broker(replies: dict[str, object] | None) -> MagicMock:
    """`celery_app` whose `inspect().ping()` returns `replies`."""
    celery = MagicMock()
    celery.control.inspect.return_value.ping.return_value = replies
    return celery


def test_ok_with_the_number_of_workers() -> None:
    replies = {"celery@a": {"ok": "pong"}, "celery@b": {"ok": "pong"}}
    with patch.object(worker_health, "celery_app", _broker(replies)):
        resp = TestClient(app).get("/health/worker")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "workers": 2}


def test_503_when_no_worker_replies() -> None:
    with patch.object(worker_health, "celery_app", _broker(None)):
        resp = TestClient(app).get("/health/worker")

    assert resp.status_code == 503
    assert resp.json() == {"status": "unavailable", "workers": 0}


def test_503_when_the_broker_is_down() -> None:
    celery = _broker(None)
    celery.connection_for_read.side_effect = OperationalError("refused")
    with patch.object(worker_health, "celery_app", celery):
        resp = TestClient(app).get("/health/worker")

    assert resp.status_code == 503
    assert resp.json()["status"] == "unavailable"


def test_each_ping_bounds_its_own_broker_connection() -> None:
    """On the shared pool a silent Redis would hold the thread forever."""
    celery = _broker(None)
    with patch.object(worker_health, "celery_app", celery):
        TestClient(app).get("/health/worker")

    options = celery.connection_for_read.call_args.kwargs["transport_options"]
    assert options["socket_timeout"] > 0
    assert options["socket_connect_timeout"] > 0
    assert celery.control.inspect.call_args.kwargs["connection"] is (
        celery.connection_for_read.return_value.__enter__.return_value
    )


async def test_a_hung_ping_blocks_neither_the_caller_nor_the_event_loop() -> None:
    release = threading.Event()
    celery = _broker(None)
    celery.control.inspect.return_value.ping.side_effect = lambda: release.wait(5)
    ticks = 0

    async def tick() -> None:
        nonlocal ticks
        while True:
            await asyncio.sleep(0.01)
            ticks += 1

    ticker = asyncio.create_task(tick())
    try:
        with (
            patch.object(worker_health, "celery_app", celery),
            patch.object(worker_health, "_DEADLINE_SECONDS", 0.1),
            pytest.raises(TimeoutError),
        ):
            await worker_health.count_workers()
    finally:
        ticker.cancel()
        release.set()

    assert ticks >= 3


async def test_concurrent_callers_share_one_ping() -> None:
    """Thirty pings at once exhaust kombu's limit; `/health` is public."""
    release = threading.Event()
    celery = _broker({"celery@a": {"ok": "pong"}})
    ping = celery.control.inspect.return_value.ping
    ping.side_effect = lambda: release.wait(5) and {"celery@a": {"ok": "pong"}}

    with patch.object(worker_health, "celery_app", celery):
        callers = [
            asyncio.create_task(worker_health.count_workers()) for _ in range(30)
        ]
        await asyncio.sleep(0.05)
        release.set()
        assert await asyncio.gather(*callers) == [1] * 30

    assert ping.call_count == 1


async def test_a_caller_past_the_deadline_leaves_the_ping_for_the_next_one() -> None:
    release = threading.Event()
    celery = _broker(None)
    ping = celery.control.inspect.return_value.ping
    ping.side_effect = lambda: release.wait(5) and {"celery@a": {"ok": "pong"}}

    with patch.object(worker_health, "celery_app", celery):
        with (
            patch.object(worker_health, "_DEADLINE_SECONDS", 0.05),
            pytest.raises(TimeoutError),
        ):
            await worker_health.count_workers()

        next_caller = asyncio.create_task(worker_health.count_workers())
        await asyncio.sleep(0.05)
        release.set()
        assert await next_caller == 1

    assert ping.call_count == 1
