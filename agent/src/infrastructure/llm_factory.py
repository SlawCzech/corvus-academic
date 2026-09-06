"""LLM factory — which model answers, and on whose account.

Two ways in, in priority order:

1. **BYOK** — the promoter's own provider key, travelling with one task. It is
   held in a ContextVar for the duration of that task rather than in the graph
   state, so it cannot reach a node's `state.copy()`, a LangGraph checkpoint,
   or the persisted result.
2. **The service's own backend** (`MODEL_BACKEND`) — self-hosted Ollama by
   default, which is what runs when nobody brought a key.
"""

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from src.infrastructure.settings import settings

# Model per provider when the user brings the key. Deliberately not the
# caller's `model` argument: that names an Ollama tag, and handing "qwen3:30b"
# to Anthropic would just fail.
_BYOK_MODELS: dict[str, str] = {
    "claude": "claude-sonnet-4-20250514",
    "openai": "gpt-4o",
}


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


def get_llm(
    model_override: str | None = None,
    credentials: ModelCredentials | None = None,
) -> BaseChatModel:
    """Return the chat model this call should use.

    A user's own key wins over the service's backend; `model_override` names
    an Ollama tag and applies only to the self-hosted path.
    """
    byok = credentials or current_credentials()
    if byok is not None:
        return _byok_model(byok)

    match settings.model_backend:
        case "claude":
            return ChatAnthropic(  # pyright: ignore[reportCallIssue]
                model=_BYOK_MODELS["claude"],  # pyright: ignore[reportCallIssue]
                anthropic_api_key=settings.anthropic_api_key,  # pyright: ignore[reportCallIssue]
            )
        case "ollama":
            return ChatOllama(  # pyright: ignore[reportCallIssue]
                model=model_override or settings.ollama_model,
                base_url=settings.ollama_base_url,
            )
        case "openai":
            return ChatOpenAI(model=_BYOK_MODELS["openai"])  # pyright: ignore[reportCallIssue]
        case _:
            raise ValueError(f"Unknown MODEL_BACKEND: {settings.model_backend!r}")


def _byok_model(credentials: ModelCredentials) -> BaseChatModel:
    """Build a model on the user's own account."""
    match credentials.provider:
        case "claude":
            return ChatAnthropic(  # pyright: ignore[reportCallIssue]
                model=_BYOK_MODELS["claude"],  # pyright: ignore[reportCallIssue]
                anthropic_api_key=credentials.api_key,  # pyright: ignore[reportCallIssue]
            )
        case _:
            return ChatOpenAI(  # pyright: ignore[reportCallIssue]
                model=_BYOK_MODELS["openai"],
                api_key=SecretStr(credentials.api_key),
            )
