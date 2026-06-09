"""Application settings loaded from environment variables."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the agent service."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    model_backend: str = "ollama"
    ollama_model: str = "qwen3:30b-a3b"
    ollama_base_url: str = "http://ollama:11434"
    anthropic_api_key: str = ""
    langchain_tracing_v2: bool = False
    langchain_project: str = "corvus"

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = Field(
        ...,
        description="PostgreSQL DSN, e.g. postgresql+asyncpg://user:pass@host:5432/db",
    )

    # Shared JWT secret — used for local token verification (no network call).
    jwt_secret: str = Field(..., min_length=32)  # noqa: S105
    jwt_algorithm: str = "HS256"


settings = Settings()
