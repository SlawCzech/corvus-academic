"""Tests for telling a provider's account problem from any other failure."""

from typing import Any

import anthropic
import httpx
import openai
import pytest

from src.domain.action import ActionErrorCode
from src.infrastructure.provider_errors import (
    ProviderAccountError,
    classify,
    raise_if_provider_error,
)

_REQUEST = httpx.Request("POST", "https://provider.test/v1/messages")


def _response(status: int, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(status, request=_REQUEST, headers=headers)


def _anthropic_body(kind: str, message: str) -> dict[str, Any]:
    return {"type": "error", "error": {"type": kind, "message": message}}


def test_anthropic_low_balance_is_no_credits() -> None:
    exc = anthropic.BadRequestError(
        "Error code: 400",
        response=_response(400),
        body=_anthropic_body(
            "invalid_request_error",
            "Your credit balance is too low to access the Anthropic API.",
        ),
    )

    problem = classify(exc)

    assert problem is not None
    assert problem.code is ActionErrorCode.PROVIDER_NO_CREDITS
    assert problem.provider == "anthropic"
    assert "credit balance is too low" in str(problem)
    assert not problem.retryable


def test_anthropic_billing_error_type_is_no_credits() -> None:
    exc = anthropic.APIStatusError(
        "Error code: 402",
        response=_response(402),
        body=_anthropic_body("billing_error", "Payment required."),
    )

    problem = classify(exc)

    assert problem is not None
    assert problem.code is ActionErrorCode.PROVIDER_NO_CREDITS


def test_anthropic_bad_request_about_the_input_is_not_an_account_problem() -> None:
    exc = anthropic.BadRequestError(
        "Error code: 400",
        response=_response(400),
        body=_anthropic_body("invalid_request_error", "prompt is too long"),
    )

    assert classify(exc) is None


@pytest.mark.parametrize(
    ("error_cls", "status"),
    [
        (anthropic.AuthenticationError, 401),
        (anthropic.PermissionDeniedError, 403),
    ],
)
def test_anthropic_refused_key(
    error_cls: type[anthropic.APIStatusError], status: int
) -> None:
    exc = error_cls(
        "refused",
        response=_response(status),
        body=_anthropic_body("authentication_error", "invalid x-api-key"),
    )

    problem = classify(exc)

    assert problem is not None
    assert problem.code is ActionErrorCode.PROVIDER_KEY_REJECTED
    assert not problem.retryable


def test_anthropic_rate_limit_is_retryable_after_what_it_asked() -> None:
    exc = anthropic.RateLimitError(
        "Error code: 429",
        response=_response(429, {"retry-after": "30"}),
        body=_anthropic_body("rate_limit_error", "Number of requests exceeded"),
    )

    problem = classify(exc)

    assert problem is not None
    assert problem.code is ActionErrorCode.PROVIDER_RATE_LIMITED
    assert problem.retryable
    assert problem.retry_after == 30.0


def test_openai_insufficient_quota_is_no_credits_not_a_rate_limit() -> None:
    exc = openai.RateLimitError(
        "You exceeded your current quota",
        response=_response(429),
        body={
            "message": "You exceeded your current quota",
            "code": "insufficient_quota",
        },
    )

    problem = classify(exc)

    assert problem is not None
    assert problem.code is ActionErrorCode.PROVIDER_NO_CREDITS
    assert problem.provider == "openai"


def test_openai_plain_rate_limit_is_retryable() -> None:
    exc = openai.RateLimitError(
        "Rate limit reached",
        response=_response(429, {"retry-after": "not a number"}),
        body={"message": "Rate limit reached", "code": "rate_limit_exceeded"},
    )

    problem = classify(exc)

    assert problem is not None
    assert problem.code is ActionErrorCode.PROVIDER_RATE_LIMITED
    assert problem.retry_after is None


def test_openai_refused_key() -> None:
    exc = openai.AuthenticationError(
        "Incorrect API key provided",
        response=_response(401),
        body={"message": "Incorrect API key provided", "code": "invalid_api_key"},
    )

    problem = classify(exc)

    assert problem is not None
    assert problem.code is ActionErrorCode.PROVIDER_KEY_REJECTED


def test_server_trouble_stays_an_ordinary_failure() -> None:
    exc = anthropic.InternalServerError(
        "Overloaded",
        response=_response(529),
        body=_anthropic_body("overloaded_error", "Overloaded"),
    )

    assert classify(exc) is None
    assert classify(ValueError("bad JSON")) is None


def test_raise_if_provider_error_lets_other_failures_pass() -> None:
    raise_if_provider_error(ValueError("bad JSON"))


def test_raise_if_provider_error_raises_the_account_problem() -> None:
    exc = openai.AuthenticationError(
        "Incorrect API key provided", response=_response(401), body=None
    )

    with pytest.raises(ProviderAccountError) as raised:
        raise_if_provider_error(exc)

    assert raised.value.__cause__ is exc


def test_survives_being_rebuilt_from_its_args() -> None:
    """Celery rebuilds a task's exception as ``cls(*args)`` after JSON."""
    original = ProviderAccountError(
        ActionErrorCode.PROVIDER_NO_CREDITS, "anthropic", "no money", None
    )
    wire = [str(a) if isinstance(a, ActionErrorCode) else a for a in original.args]

    rebuilt = ProviderAccountError(*wire)

    assert rebuilt.code is ActionErrorCode.PROVIDER_NO_CREDITS
    assert str(rebuilt) == str(original)
