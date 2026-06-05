"""Gateway configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All gateway configuration, sourced from env or .env file."""

    jwt_secret: str = "dev-secret-change-in-production-min-32-chars"  # noqa: S105
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/thesis_reviewer"
    # 32-byte dev key (base64url of b"\x00"*32) — override via FERNET_KEY env var
    fernet_key: str = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="  # noqa: S105

    admin_email: str = "admin@corvus.local"
    admin_password: str = ""  # noqa: S105

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
