"""Shared test fixtures and env setup for agent tests."""

import os

# Must be set before any src.* import that triggers settings initialisation.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/thesis_reviewer"
)
os.environ.setdefault("JWT_SECRET", "test-secret-key-that-is-long-enough-32ch")
os.environ.setdefault("CHECKPOINTS_ENABLED", "false")
