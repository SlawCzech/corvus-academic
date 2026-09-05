"""Application configuration loaded from environment variables.

Merged from the former identity and gateway settings modules — the two
services are now one deployable (`app`), so they share one Settings object.
"""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All `app` configuration, sourced from env or .env file.

    Required variables (no defaults — missing value raises ValidationError
    at startup): JWT_SECRET, FERNET_KEY, DATABASE_URL, ADMIN_PASSWORD, AGENT_URL.
    """

    # Deployment environment — drives cookie security, log verbosity, defaults.
    environment: Literal["local", "production"] = "local"

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

    # Downstream services still reached over HTTP.
    agent_url: str = Field(..., description="Base URL of the agent service")

    cors_origins: list[str] = Field(
        default=["http://localhost:3000"],
        description="Allowed CORS origins",
    )

    @property
    def cookie_secure(self) -> bool:
        """Whether auth cookies carry the Secure flag.

        False under `local` so plain-HTTP development still receives the
        refresh cookie; True in production, where HTTPS is expected.
        """
        return self.environment == "production"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
