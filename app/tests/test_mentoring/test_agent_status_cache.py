"""Polling an action asks the agent at most once per moment."""

import httpx

from src.mentoring.application.agent_client import (
    AgentActionStatus,
    AgentClient,
    StatusCache,
)


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def _client(calls: list[str], cache: StatusCache | None) -> AgentClient:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path.endswith("/cancel"):
            return httpx.Response(200, json={"status": "cancelled"})
        return httpx.Response(200, json={"status": "running"})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return AgentClient(http, "http://agent", cache)


async def test_a_second_poll_within_the_moment_is_answered_from_the_cache() -> None:
    calls: list[str] = []
    clock = Clock()
    agent = _client(calls, StatusCache(ttl_seconds=2, clock=clock))

    await agent.get_action("t1", "token")
    clock.now += 1.9
    assert (await agent.get_action("t1", "token")).status == "running"

    assert calls == ["GET /actions/t1"]


async def test_the_agent_is_asked_again_once_the_moment_is_over() -> None:
    calls: list[str] = []
    clock = Clock()
    agent = _client(calls, StatusCache(ttl_seconds=2, clock=clock))

    await agent.get_action("t1", "token")
    clock.now += 2
    await agent.get_action("t1", "token")

    assert calls == ["GET /actions/t1", "GET /actions/t1"]


async def test_cancelling_drops_the_cached_status() -> None:
    calls: list[str] = []
    agent = _client(calls, StatusCache(ttl_seconds=60, clock=Clock()))

    await agent.get_action("t1", "token")
    await agent.cancel_action("t1", "token")
    await agent.get_action("t1", "token")

    assert calls == ["GET /actions/t1", "POST /actions/t1/cancel", "GET /actions/t1"]


async def test_without_a_cache_every_poll_reaches_the_agent() -> None:
    calls: list[str] = []
    agent = _client(calls, None)

    await agent.get_action("t1", "token")
    await agent.get_action("t1", "token")

    assert len(calls) == 2


def test_expired_entries_are_dropped_on_write() -> None:
    clock = Clock()
    cache = StatusCache(ttl_seconds=2, clock=clock)
    cache.put("old", _status())
    clock.now += 5
    cache.put("new", _status())

    assert cache.get("old") is None
    assert cache._entries.keys() == {"new"}  # pyright: ignore[reportPrivateUsage]


def _status() -> AgentActionStatus:
    return AgentActionStatus(status="running", result=None, error=None)
