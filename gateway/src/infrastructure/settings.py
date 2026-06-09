"""Gateway configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All gateway configuration, sourced from env or .env file."""

    redis_url: str = "redis://localhost:6379/0"

    # Base URLs of downstream services.
    identity_url: str = "http://identity:8003"
    agent_url: str = "http://agent:8002"

    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
