"""LLM factory — placeholder; full model selector comes in session 2.3."""

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel

from src.infrastructure.settings import settings


def get_llm() -> BaseChatModel:
    """Return a Claude Sonnet instance configured from environment settings."""
    # pyright can't see ChatAnthropic's Pydantic-generated constructor params
    return ChatAnthropic(
        model="claude-sonnet-4-20250514", anthropic_api_key=settings.anthropic_api_key
    )  # pyright: ignore[reportCallIssue]
