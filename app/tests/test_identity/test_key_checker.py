"""Tests for checking a provider key over HTTP."""

import httpx
import pytest

from src.identity.application.key_check import KeyVerdict
from src.identity.infrastructure.key_checker import HttpKeyChecker


def _checker(handler: httpx.MockTransport) -> HttpKeyChecker:
    return HttpKeyChecker(httpx.AsyncClient(transport=handler))


async def test_anthropic_key_goes_in_its_own_header() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"data": []})

    verdict = await _checker(httpx.MockTransport(handler)).check("claude", "sk-ant-x")

    assert verdict is KeyVerdict.ACCEPTED
    assert seen[0].url.host == "api.anthropic.com"
    assert seen[0].headers["x-api-key"] == "sk-ant-x"
    assert "anthropic-version" in seen[0].headers


async def test_openai_key_goes_as_a_bearer_token() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"data": []})

    verdict = await _checker(httpx.MockTransport(handler)).check("openai", "sk-x")

    assert verdict is KeyVerdict.ACCEPTED
    assert seen[0].url.host == "api.openai.com"
    assert seen[0].headers["authorization"] == "Bearer sk-x"


@pytest.mark.parametrize("status", [401, 403])
async def test_refused_key_is_rejected(status: int) -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(status))

    verdict = await _checker(transport).check("claude", "sk-ant-x")

    assert verdict is KeyVerdict.REJECTED


@pytest.mark.parametrize("status", [429, 500, 529])
async def test_provider_trouble_says_nothing_about_the_key(status: int) -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(status))

    verdict = await _checker(transport).check("openai", "sk-x")

    assert verdict is KeyVerdict.UNCHECKED


async def test_no_network_leaves_the_key_unchecked() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    verdict = await _checker(httpx.MockTransport(handler)).check("claude", "sk-ant-x")

    assert verdict is KeyVerdict.UNCHECKED
