"""Tests for the LLM factory: the promoter's key, and only that."""

from unittest.mock import patch

import pytest

from src.infrastructure.llm_factory import (
    MissingCredentialsError,
    ModelCredentials,
    current_credentials,
    get_llm,
    model_label,
    use_credentials,
)

# ---------- BYOK ----------


def _byok(provider: str = "claude", key: str = "sk-user-key") -> ModelCredentials:
    return ModelCredentials(provider=provider, api_key=key)


def test_the_users_key_reaches_the_provider() -> None:
    with patch("src.infrastructure.llm_factory.ChatAnthropic") as anthropic:
        get_llm(credentials=_byok())

    assert anthropic.call_args.kwargs["anthropic_api_key"] == "sk-user-key"
    assert anthropic.call_args.kwargs["model"] == "claude-sonnet-5-5"


def test_without_a_key_there_is_no_model() -> None:
    """No service model to fall back on: someone else's account never pays."""
    with pytest.raises(MissingCredentialsError):
        get_llm()


def test_the_label_is_the_providers_model() -> None:
    assert model_label(_byok(provider="openai")) == "gpt-6.1-sol"
    assert model_label(None) == "none"


def test_openai_key_is_passed_as_a_secret() -> None:
    with patch("src.infrastructure.llm_factory.ChatOpenAI") as openai:
        get_llm(credentials=_byok(provider="openai", key="sk-openai"))

    assert openai.call_args.kwargs["api_key"].get_secret_value() == "sk-openai"


def test_credentials_apply_to_the_block_that_set_them() -> None:
    """Nodes call get_llm() with no arguments; the key travels out of band."""
    with patch("src.infrastructure.llm_factory.ChatAnthropic") as anthropic:
        with use_credentials(_byok()):
            get_llm()
        assert anthropic.call_count == 1

        # Outside the block there is no key — a prefork worker must not
        # inherit the previous caller's.
        with pytest.raises(MissingCredentialsError):
            get_llm()

    assert current_credentials() is None


def test_claude_gets_room_to_think_and_an_explicit_effort() -> None:
    """Left to LangChain's fallback, 4096 tokens would cut a review short."""
    with (
        patch("src.infrastructure.llm_factory.settings") as mock_settings,
        patch("src.infrastructure.llm_factory.ChatAnthropic") as anthropic,
    ):
        mock_settings.anthropic_effort = "medium"
        get_llm(credentials=_byok())

    kwargs = anthropic.call_args.kwargs
    assert kwargs["max_tokens"] == 16000
    assert kwargs["effort"] == "medium"
    # A connection that goes quiet must not hold a review for the SDK's ten
    # minutes, three times over.
    assert kwargs["timeout"] == 180.0
    assert kwargs["max_retries"] == 1


def test_unsupported_provider_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported provider"):
        ModelCredentials(provider="deepmind", api_key="k")


def test_empty_key_is_rejected() -> None:
    with pytest.raises(ValueError, match="api_key"):
        ModelCredentials(provider="claude", api_key="")
