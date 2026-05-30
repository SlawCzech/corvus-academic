"""Gateway configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All gateway configuration, sourced from env or .env file."""

    jwt_secret: str = "dev-secret-change-in-production-min-32-chars"  # noqa: S105
    jwt_algorithm: str = "HS256"
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/thesis_reviewer"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
