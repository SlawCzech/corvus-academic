"""Environment defaults for the whole `app` test suite.

Loaded before any subdirectory conftest, so importing `main` (and therefore
`src.shared.settings`) never fails on a missing required variable.
"""

import os

os.environ.setdefault("JWT_SECRET", "test-secret-key-that-is-long-enough-32ch")
os.environ.setdefault("FERNET_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/thesis_reviewer"
)
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password-123")
os.environ.setdefault("AGENT_URL", "http://agent:8002")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
