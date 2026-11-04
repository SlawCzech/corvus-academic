"""LLM factory — which model answers, and on whose account.

Always the promoter's own provider key (BYOK), travelling with one task. It
is held in a ContextVar for the duration of that task rather than in the
graph state, so it cannot reach a node's `state.copy()`, a LangGraph
checkpoint, or the persisted result. There is no service model to fall back
on (ADR 0022): a run without a key fails rather than runs on someone else's.
"""

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from src.infrastructure.settings import settings

# The model each provider runs on.
_BYOK_MODELS: dict[str, str] = {
    "claude": "claude-sonnet-5-5",
    # OpenAI's counterpart of Sonnet: "near-flagship at a lower cost", and the
    # same price per token. Checked against the key's model list 2026-10-01.
    "openai": "gpt-6.1-sol",
}

# Thinking counts toward the limit even though its text is not returned, and
# a review is the longest reply any action asks for. Left unset, LangChain
# falls back to 4096 for a model it has no profile for — a truncated JSON.
_CLAUDE_MAX_TOKENS = 16000

# One call to a provider, in seconds. The SDKs wait ten minutes by default and
# then try again twice — half an hour before a connection that went quiet
# becomes a failed action. The longest call seen on a full thesis took half a
# minute.
_REQUEST_TIMEOUT = 180.0


def byok_models() -> dict[str, str]:
    """The model each provider runs on when the user brings the key."""
    return dict(_BYOK_MODELS)


@dataclass(frozen=True)
class ModelCredentials:
    """One user's own provider key, for the length of one task."""

    provider: str
    api_key: str

    def __post_init__(self) -> None:
        if self.provider not in _BYOK_MODELS:
            raise ValueError(f"Unsupported provider: {self.provider!r}")
        if not self.api_key:
            raise ValueError("api_key must not be empty")


_credentials: ContextVar[ModelCredentials | None] = ContextVar(
    "model_credentials", default=None
)


@contextmanager
def use_credentials(credentials: ModelCredentials | None) -> Generator[None]:
    """Run a block with one user's key in effect, and only that block.

    Reset in a finally so a prefork worker that reuses this process for the
    next task cannot inherit the previous caller's key.
    """
    token = _credentials.set(credentials)
    try:
        yield
    finally:
        _credentials.reset(token)


def current_credentials() -> ModelCredentials | None:
    """Return the credentials in effect, if any."""
    return _credentials.get()


class MissingCredentialsError(ValueError):
    """A model was asked for outside any promoter's key."""


def model_label(credentials: ModelCredentials | None) -> str:
    """The model a run on these credentials answers with, for traces and logs."""
    return _BYOK_MODELS[credentials.provider] if credentials else "none"


def get_llm(credentials: ModelCredentials | None = None) -> BaseChatModel:
    """Return the chat model this call should use: the promoter's, always."""
    byok = credentials or current_credentials()
    if byok is None:
        raise MissingCredentialsError("this run has no provider key")
    return _byok_model(byok)


def _claude(api_key: str) -> BaseChatModel:
    """Claude, with the two things this model needs said out loud.

    Thinking cannot be switched off on Sonnet 5.5; how much of it there is
    follows `effort`, so that is the latency and cost dial (ANTHROPIC_EFFORT).
    """
    return ChatAnthropic(  # pyright: ignore[reportCallIssue]
        model=_BYOK_MODELS["claude"],  # pyright: ignore[reportCallIssue]
        anthropic_api_key=api_key,  # pyright: ignore[reportCallIssue]
        max_tokens=_CLAUDE_MAX_TOKENS,  # pyright: ignore[reportCallIssue]
        effort=settings.anthropic_effort,
        timeout=_REQUEST_TIMEOUT,  # pyright: ignore[reportCallIssue]
        max_retries=1,
    )


def _byok_model(credentials: ModelCredentials) -> BaseChatModel:
    """Build a model on the user's own account."""
    match credentials.provider:
        case "claude":
            return _claude(credentials.api_key)
        case _:
            return ChatOpenAI(  # pyright: ignore[reportCallIssue]
                model=_BYOK_MODELS["openai"],
                api_key=SecretStr(credentials.api_key),
                timeout=_REQUEST_TIMEOUT,
                max_retries=1,
            )
