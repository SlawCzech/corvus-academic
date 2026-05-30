"""Shared test fixtures for gateway tests."""

import os

import pytest
from fastapi.testclient import TestClient

# Set env vars before importing the app so Settings picks them up.
os.environ.setdefault("JWT_SECRET", "test-secret-key-that-is-long-enough-32ch")
# Valid 32-byte Fernet key (base64url of b"\x00"*32) for deterministic test output.
os.environ.setdefault("FERNET_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")

from main import app  # noqa: E402  — import after env is set


@pytest.fixture
def client() -> TestClient:
    """Return a synchronous TestClient for the gateway app."""
    return TestClient(app)
