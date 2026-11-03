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
    # Half an hour: `get_current_user` does not ask the database, so this is how
    # long a deleted user keeps access. The refresh token renews it unseen, in
    # the middleware on a navigation and in the API client on a 401, so it can
    # expire while a review runs. Override per environment with
    # ACCESS_TOKEN_EXPIRE_MINUTES.
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = Field(
        ...,
        description="PostgreSQL DSN, e.g. postgresql+asyncpg://user:pass@host:5432/db",
    )

    admin_email: str = "admin@corvus.local"
    admin_password: str = Field(
        ...,
        min_length=12,
        description="Initial admin password (min 12 chars)",  # noqa: S105
    )

    # Downstream services still reached over HTTP.
    agent_url: str = Field(..., description="Base URL of the agent service")

    # Largest file accepted on upload. A thesis with figures runs to a few
    # megabytes; this leaves room while refusing anything absurd before it is
    # read into memory in full.
    max_upload_bytes: int = 25 * 1024 * 1024

    # Text is extracted from an upload in a child process that is killed past
    # these limits (`document/isolated.py`). A 300-page thesis reads in a few
    # seconds and well under the memory cap. Off in the test suite only, where
    # spawning a process per upload would cost minutes; its own tests keep the
    # isolated path covered.
    extraction_isolated: bool = True
    extraction_timeout_seconds: float = 60
    extraction_max_memory_bytes: int = 1024 * 1024 * 1024

    # How often the retention sweep runs in-process; 0 turns it off (tests,
    # or a deployment that runs `scripts/purge_drafts.py` from cron instead).
    retention_sweep_interval_hours: float = 24

    # Whether promoters may run actions on the server's own models (Ollama).
    # Off by default: every action goes on the promoter's own provider key, and
    # an action without one is refused — never queued for a model that may not
    # be there (ADR 0013, ADR 0016).
    local_models_enabled: bool = False

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


# Every required field is read from the environment at startup; pyright cannot
# see that, and a missing one is meant to fail loudly right here.
settings = Settings()  # pyright: ignore[reportCallIssue]
