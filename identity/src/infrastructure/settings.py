"""Identity service configuration loaded from environment variables."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All identity service configuration, sourced from env or .env file."""

    # No defaults — app fails at startup if these are not set in the environment.
    jwt_secret: str = Field(..., min_length=32)  # noqa: S105
    fernet_key: str = Field(...)  # noqa: S105

    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = Field(
        ...,
        description="PostgreSQL DSN, e.g. postgresql+asyncpg://user:pass@host:5432/db",
    )

    admin_email: str = "admin@corvus.local"
    admin_password: str = Field(
        ..., min_length=12, description="Initial admin password (min 12 chars)"  # noqa: S105
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
