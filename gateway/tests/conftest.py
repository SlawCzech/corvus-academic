"""Shared test fixtures for gateway tests."""

import os

import pytest
from fastapi.testclient import TestClient

# Provide a deterministic JWT secret so tests don't depend on .env
os.environ.setdefault("JWT_SECRET", "test-secret-key-that-is-long-enough-32ch")

from main import app  # noqa: E402  — import after env is set


@pytest.fixture
def client() -> TestClient:
    """Return a synchronous TestClient for the gateway app."""
    return TestClient(app)
