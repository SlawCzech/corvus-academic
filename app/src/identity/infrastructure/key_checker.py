"""`KeyChecker` over HTTP: list the provider's models with the key.

Listing models is free on both providers and needs nothing but a valid key,
so a 401 or 403 means the key itself is wrong. It says nothing about the
balance — an account with no credits still lists models; running out is
reported by the action that hits it (see the agent's `provider_errors`).
"""

import httpx
import structlog

from src.identity.application.key_check import KeyVerdict

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_ANTHROPIC_MODELS = "https://api.anthropic.com/v1/models?limit=1"
_ANTHROPIC_VERSION = "2023-06-01"
_OPENAI_MODELS = "https://api.openai.com/v1/models"

# Short: the promoter is waiting on the save button.
_TIMEOUT = 10.0


class HttpKeyChecker:
    """Checks a key against the provider's own API."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def check(self, provider: str, api_key: str) -> KeyVerdict:
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
            return KeyVerdict.UNCHECKED
        if response.is_success:
            return KeyVerdict.ACCEPTED
        if response.status_code in (401, 403):
            return KeyVerdict.REJECTED
        logger.warning(
            "api_key_check_inconclusive",
            provider=provider,
            status=response.status_code,
        )
        return KeyVerdict.UNCHECKED


def _request_for(provider: str, api_key: str) -> tuple[str, dict[str, str]]:
    if provider == "claude":
        return _ANTHROPIC_MODELS, {
            "x-api-key": api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
        }
    return _OPENAI_MODELS, {"Authorization": f"Bearer {api_key}"}
