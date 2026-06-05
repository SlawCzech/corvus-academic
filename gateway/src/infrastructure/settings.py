"""Gateway configuration loaded from environment variables."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All gateway configuration, sourced from env or .env file."""

    # No defaults — app fails at startup if these are not set in the environment.
    jwt_secret: str = Field(..., min_length=32)  # noqa: S105
    fernet_key: str = Field(...)  # noqa: S105

    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/thesis_reviewer"

    admin_email: str = "admin@corvus.local"
    admin_password: str = ""  # noqa: S105

    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
