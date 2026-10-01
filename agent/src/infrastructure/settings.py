"""Application settings loaded from environment variables."""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the agent service."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    model_backend: str = "ollama"
    ollama_model: str = "qwen3:30b-a3b"
    ollama_base_url: str = "http://ollama:11434"

    # Guideline retrieval. The embedding model is stored alongside every
    # chunk, so changing it here only means re-running the ingestion script —
    # rows produced by another model are ignored, never mixed in.
    embedding_model: str = "nomic-embed-text"
    rag_top_k: int = 6
    # Embeddings have their own base URL because they need not come from the
    # same server as the chat models: an OpenAI-compatible chat server
    # (llama.cpp, LM Studio) may refuse embeddings entirely, while the Ollama
    # this stack ships serves them. Defaults to the compose service.
    embedding_base_url: str = "http://ollama:11434"
    anthropic_api_key: str = ""
    # How much Claude thinks before it answers — the dial for latency and
    # cost on a model whose thinking cannot be turned off. `medium` is a
    # starting point, to be settled by the evals (`make eval MODEL=claude`).
    anthropic_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    langchain_tracing_v2: bool = False
    langchain_project: str = "corvus"

    # Self-hosted Langfuse (infra/langfuse). Tracing is on only when all three
    # are set; an empty base URL is the off switch, not an error.
    langfuse_base_url: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    # The bibliography check asks Crossref whether cited works exist. Only
    # reference strings leave the machine. The mailto puts requests in
    # Crossref's "polite pool" — an address of whoever runs this instance.
    crossref_mailto: str = ""
    crossref_timeout: float = 10.0

    # Graph checkpoints in Postgres, so a run that dies can resume. Off in
    # tests and evals, which have no database.
    checkpoints_enabled: bool = True

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = Field(
        ...,
        description="PostgreSQL DSN, e.g. postgresql+asyncpg://user:pass@host:5432/db",
    )

    # Shared JWT secret — used for local token verification (no network call).
    jwt_secret: str = Field(..., min_length=32)  # noqa: S105
    jwt_algorithm: str = "HS256"


# Every required field is read from the environment at startup; pyright cannot
# see that, and a missing one is meant to fail loudly right here.
settings = Settings()  # pyright: ignore[reportCallIssue]
