"""Telling a provider's account problem apart from a model's bad answer.

Nodes catch every exception and carry on: a model that returned nonsense for
one analysis should not cost the whole review. An account problem is not
like that. With no credits left or the key refused, every later call fails
the same way, so the run has to stop and say why, and retrying it three
times a minute apart only makes the promoter wait for the same answer.

`classify` reads the Anthropic and OpenAI SDK exceptions (LangChain passes
them through unchanged) and returns a `ProviderAccountError` for the ones
the promoter can act on. Anything else, overloaded servers and dropped
connections included, stays an ordinary failure with the usual retries.
"""

from typing import Any, cast

import anthropic
import openai

from src.domain.action import ActionErrorCode

# Anthropic answers an empty balance with a 400, and names it only in the
# message; newer responses also carry a dedicated error type.
_ANTHROPIC_NO_CREDITS_TYPE = "billing_error"
_ANTHROPIC_NO_CREDITS_TEXT = "credit balance"
# OpenAI answers an empty balance with a 429, told apart from a real rate
# limit only by this code.
_OPENAI_NO_CREDITS_CODE = "insufficient_quota"


class ProviderAccountError(Exception):
    """The provider refused the call because of the account, not the input."""

    def __init__(
        self,
        code: ActionErrorCode | str,
        provider: str,
        detail: str,
        retry_after: float | None = None,
    ) -> None:
        # `args` mirror the signature: Celery rebuilds a task's exception as
        # `cls(*args)` when it reads the result back, and a JSON round trip
        # turns the code into a plain string on the way.
        super().__init__(str(code), provider, detail, retry_after)
        self.code = ActionErrorCode(code)
        self.provider = provider
        self.detail = detail
        self.retry_after = retry_after

    def __str__(self) -> str:
        return f"{self.provider}: {self.detail}"

    @property
    def retryable(self) -> bool:
        """Whether waiting can fix it. Only a rate limit passes by itself."""
        return self.code is ActionErrorCode.PROVIDER_RATE_LIMITED


def classify(exc: BaseException) -> ProviderAccountError | None:
    """Return the account problem behind `exc`, or None if it is not one."""
    if isinstance(exc, ProviderAccountError):
        return exc
    if isinstance(exc, anthropic.APIStatusError):
        return _anthropic(exc)
    if isinstance(exc, openai.APIStatusError):
        return _openai(exc)
    return None


def raise_if_provider_error(exc: BaseException) -> None:
    """Re-raise `exc` as a `ProviderAccountError` if it is one.

    Called first in a node's catch-all, so the node goes on swallowing what
    it should (a bad reply) and lets through what it must not (a dead account).
    """
    problem = classify(exc)
    if problem is not None:
        raise problem from exc


def _anthropic(exc: anthropic.APIStatusError) -> ProviderAccountError | None:
    detail = _anthropic_message(exc)
    if isinstance(exc, anthropic.RateLimitError):
        return ProviderAccountError(
            ActionErrorCode.PROVIDER_RATE_LIMITED,
            "anthropic",
            detail,
            retry_after=_retry_after(exc.response.headers),
        )
    if isinstance(exc, anthropic.AuthenticationError | anthropic.PermissionDeniedError):
        return ProviderAccountError(
            ActionErrorCode.PROVIDER_KEY_REJECTED, "anthropic", detail
        )
    if (
        _anthropic_error_type(exc) == _ANTHROPIC_NO_CREDITS_TYPE
        or _ANTHROPIC_NO_CREDITS_TEXT in detail.lower()
    ):
        return ProviderAccountError(
            ActionErrorCode.PROVIDER_NO_CREDITS, "anthropic", detail
        )
    return None


def _openai(exc: openai.APIStatusError) -> ProviderAccountError | None:
    detail = exc.message
    if isinstance(exc, openai.RateLimitError):
        if exc.code == _OPENAI_NO_CREDITS_CODE:
            return ProviderAccountError(
                ActionErrorCode.PROVIDER_NO_CREDITS, "openai", detail
            )
        return ProviderAccountError(
            ActionErrorCode.PROVIDER_RATE_LIMITED,
            "openai",
            detail,
            retry_after=_retry_after(exc.response.headers),
        )
    if isinstance(exc, openai.AuthenticationError | openai.PermissionDeniedError):
        return ProviderAccountError(
            ActionErrorCode.PROVIDER_KEY_REJECTED, "openai", detail
        )
    return None


def _anthropic_error(exc: anthropic.APIStatusError) -> dict[str, Any]:
    body: Any = exc.body
    if not isinstance(body, dict):
        return {}
    error: Any = cast(dict[str, Any], body).get("error")
    return cast(dict[str, Any], error) if isinstance(error, dict) else {}


def _anthropic_error_type(exc: anthropic.APIStatusError) -> str:
    return str(_anthropic_error(exc).get("type", ""))


def _anthropic_message(exc: anthropic.APIStatusError) -> str:
    """The provider's own sentence, without the SDK's status-code prefix."""
    return str(_anthropic_error(exc).get("message") or exc.message)


def _retry_after(headers: Any) -> float | None:  # noqa: ANN401 — httpx.Headers
    raw: Any = headers.get("retry-after")
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None
