"""LLM factory — returns a configured chat model based on MODEL_BACKEND setting."""

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from src.infrastructure.settings import settings


def get_llm() -> BaseChatModel:
    """Return a chat model instance configured by MODEL_BACKEND env variable."""
    match settings.model_backend:
        case "claude":
            return ChatAnthropic(  # pyright: ignore[reportCallIssue]
                model="claude-sonnet-4-20250514",  # pyright: ignore[reportCallIssue]
                anthropic_api_key=settings.anthropic_api_key,  # pyright: ignore[reportCallIssue]
            )
        case "ollama":
            return ChatOllama(  # pyright: ignore[reportCallIssue]
                model=settings.ollama_model,
                base_url=settings.ollama_base_url,
            )
        case "openai":
            return ChatOpenAI(model="gpt-4o")  # pyright: ignore[reportCallIssue]
        case _:
            raise ValueError(f"Unknown MODEL_BACKEND: {settings.model_backend!r}")
