"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the agent service."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    model_backend: str = "claude"
    ollama_model: str = "qwen3.6:14b"
    ollama_base_url: str = "http://ollama:11434"
    anthropic_api_key: str = ""
    langchain_tracing_v2: bool = False
    langchain_project: str = "corvus"
    redis_url: str = "redis://localhost:6379/0"


settings = Settings()
