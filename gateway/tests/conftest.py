"""Shared test fixtures for gateway tests."""

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("IDENTITY_URL", "http://identity:8003")
os.environ.setdefault("AGENT_URL", "http://agent:8002")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from main import app  # noqa: E402


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
