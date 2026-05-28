"""Tests for the LLM factory model selector."""

from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.llm_factory import get_llm


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
