"""Tests for the LLM factory model selector."""

from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.llm_factory import (
    ModelCredentials,
    current_credentials,
    get_llm,
    use_credentials,
)


@pytest.mark.parametrize("backend", ["claude", "ollama", "openai"])
def test_get_llm_returns_model_for_backend(backend: str) -> None:
    """get_llm returns a chat model instance for each supported backend."""
    mock_instance = MagicMock()
    constructor_map = {
        "claude": "src.infrastructure.llm_factory.ChatAnthropic",
        "ollama": "src.infrastructure.llm_factory.ChatOllama",
        "openai": "src.infrastructure.llm_factory.ChatOpenAI",
    }
    with (
        patch("src.infrastructure.llm_factory.settings") as mock_settings,
        patch(constructor_map[backend], return_value=mock_instance),
    ):
        mock_settings.model_backend = backend
        mock_settings.anthropic_api_key = "test-key"
        mock_settings.ollama_model = "llama3"
        mock_settings.ollama_base_url = "http://localhost:11434"
        result = get_llm()

    assert result is mock_instance


def test_get_llm_raises_for_unknown_backend() -> None:
    """get_llm raises ValueError when MODEL_BACKEND is unrecognised."""
    with patch("src.infrastructure.llm_factory.settings") as mock_settings:
        mock_settings.model_backend = "unknown_provider"
        with pytest.raises(ValueError, match="Unknown MODEL_BACKEND"):
            get_llm()


def test_get_llm_claude_passes_api_key() -> None:
    """ChatAnthropic is constructed with the api key from settings."""
    with (
        patch("src.infrastructure.llm_factory.settings") as mock_settings,
        patch("src.infrastructure.llm_factory.ChatAnthropic") as mock_cls,
    ):
        mock_settings.model_backend = "claude"
        mock_settings.anthropic_api_key = "sk-ant-test"
        get_llm()
        call_kwargs = mock_cls.call_args.kwargs
        assert call_kwargs.get("anthropic_api_key") == "sk-ant-test"


def test_get_llm_ollama_passes_model_and_url() -> None:
    """ChatOllama is constructed with model name and base_url from settings."""
    with (
        patch("src.infrastructure.llm_factory.settings") as mock_settings,
        patch("src.infrastructure.llm_factory.ChatOllama") as mock_cls,
    ):
        mock_settings.model_backend = "ollama"
        mock_settings.ollama_model = "qwen3"
        mock_settings.ollama_base_url = "http://ollama:11434"
        get_llm()
        call_kwargs = mock_cls.call_args.kwargs
        assert call_kwargs.get("model") == "qwen3"
        assert call_kwargs.get("base_url") == "http://ollama:11434"


# ---------- BYOK ----------


def _byok(provider: str = "claude", key: str = "sk-user-key") -> ModelCredentials:
    return ModelCredentials(provider=provider, api_key=key)


def test_users_own_key_wins_over_the_service_backend() -> None:
    """A promoter who brought a key does not get the self-hosted model."""
    with (
        patch("src.infrastructure.llm_factory.settings") as mock_settings,
        patch("src.infrastructure.llm_factory.ChatAnthropic") as anthropic,
        patch("src.infrastructure.llm_factory.ChatOllama") as ollama,
    ):
        mock_settings.model_backend = "ollama"
        get_llm("qwen3:30b-a3b", credentials=_byok())

    ollama.assert_not_called()
    assert anthropic.call_args.kwargs["anthropic_api_key"] == "sk-user-key"


def test_openai_key_is_passed_as_a_secret() -> None:
    with (
        patch("src.infrastructure.llm_factory.settings") as mock_settings,
        patch("src.infrastructure.llm_factory.ChatOpenAI") as openai,
    ):
        mock_settings.model_backend = "ollama"
        get_llm(credentials=_byok(provider="openai", key="sk-openai"))

    assert openai.call_args.kwargs["api_key"].get_secret_value() == "sk-openai"


def test_credentials_apply_to_the_block_that_set_them() -> None:
    """Nodes call get_llm() with no arguments; the key travels out of band."""
    with (
        patch("src.infrastructure.llm_factory.settings") as mock_settings,
        patch("src.infrastructure.llm_factory.ChatAnthropic") as anthropic,
        patch("src.infrastructure.llm_factory.ChatOllama") as ollama,
    ):
        mock_settings.model_backend = "ollama"
        mock_settings.ollama_model = "qwen3"
        mock_settings.ollama_base_url = "http://localhost:11434"

        with use_credentials(_byok()):
            get_llm()
        assert anthropic.call_count == 1

        # Outside the block the service is back on its own model — a prefork
        # worker must not inherit the previous caller's key.
        get_llm()

    assert current_credentials() is None
    ollama.assert_called_once()


def test_model_override_does_not_apply_to_a_users_provider() -> None:
    """`model` names an Ollama tag; handing it to Anthropic would just fail."""
    with (
        patch("src.infrastructure.llm_factory.settings") as mock_settings,
        patch("src.infrastructure.llm_factory.ChatAnthropic") as anthropic,
    ):
        mock_settings.model_backend = "ollama"
        get_llm("qwen3:30b-a3b", credentials=_byok())

    assert anthropic.call_args.kwargs["model"] == "claude-sonnet-5-5"


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


def test_unsupported_provider_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported provider"):
        ModelCredentials(provider="deepmind", api_key="k")


def test_empty_key_is_rejected() -> None:
    with pytest.raises(ValueError, match="api_key"):
        ModelCredentials(provider="claude", api_key="")
