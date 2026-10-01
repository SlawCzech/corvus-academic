"""`KeyChecker` over HTTP: list the provider's models with the key.

Listing models is free on both providers and needs nothing but a valid key,
so a refusal is about the key: a 401 or 403 means it is wrong, any other 4xx
that it cannot be used as sent. It says nothing about the
balance — an account with no credits still lists models; running out is
reported by the action that hits it (see the agent's `provider_errors`).
"""

from typing import Any, cast

import httpx
import structlog

from src.identity.application.key_check import KeyCheck, KeyVerdict

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_ANTHROPIC_MODELS = "https://api.anthropic.com/v1/models?limit=1"
_ANTHROPIC_VERSION = "2023-06-01"
_OPENAI_MODELS = "https://api.openai.com/v1/models"

# Short: the promoter is waiting on the save button.
_TIMEOUT = 10.0
# A 4xx that is the provider asking for patience, not refusing the key.
_NOT_ABOUT_THE_KEY = {408, 429}
_MESSAGE_CHARS = 400


class HttpKeyChecker:
    """Checks a key against the provider's own API."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def check(self, provider: str, api_key: str) -> KeyCheck:
        url, headers = _request_for(provider, api_key)
        try:
            response = await self._client.get(url, headers=headers, timeout=_TIMEOUT)
        except httpx.HTTPError as exc:
            # Never the key: the exception may carry the request, not its body.
            logger.warning(
                "api_key_check_unreachable",
                provider=provider,
                error=type(exc).__name__,
            )
            return KeyCheck(KeyVerdict.UNCHECKED)
        if response.is_success:
            return KeyCheck(KeyVerdict.ACCEPTED)
        status = response.status_code
        if 400 <= status < 500 and status not in _NOT_ABOUT_THE_KEY:
            return KeyCheck(KeyVerdict.REJECTED, _provider_message(response, api_key))
        logger.warning("api_key_check_inconclusive", provider=provider, status=status)
        return KeyCheck(KeyVerdict.UNCHECKED)


def _provider_message(response: httpx.Response, api_key: str) -> str | None:
    """What the provider said was wrong, if it said so in the usual place.

    Both providers answer ``{"error": {"message": …}}``. The key is cut out in
    case the provider quotes it back.
    """
    try:
        body: Any = response.json()
    except ValueError:
        return None
    if not isinstance(body, dict):
        return None
    error = cast(dict[str, Any], body).get("error")
    if not isinstance(error, dict):
        return None
    message = cast(dict[str, Any], error).get("message")
    if not isinstance(message, str) or not message.strip():
        return None
    return message.replace(api_key, "…").strip()[:_MESSAGE_CHARS]


def _request_for(provider: str, api_key: str) -> tuple[str, dict[str, str]]:
    if provider == "claude":
        return _ANTHROPIC_MODELS, {
            "x-api-key": api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
        }
    return _OPENAI_MODELS, {"Authorization": f"Bearer {api_key}"}
