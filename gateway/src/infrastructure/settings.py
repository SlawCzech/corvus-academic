"""Gateway configuration loaded from environment variables."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All gateway configuration, sourced from env or .env file.

    Required variables (no defaults — missing value raises ValidationError on startup):
      IDENTITY_URL, AGENT_URL, REDIS_URL

    Optional variables (safe defaults for local development):
      CORS_ORIGINS
    """

    identity_url: str = Field(..., description="Base URL of the identity service")
    agent_url: str = Field(..., description="Base URL of the agent service")
    redis_url: str = Field(..., description="Redis connection URL")

    cors_origins: list[str] = Field(
        default=["http://localhost:3000"],
        description="Allowed CORS origins",
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
