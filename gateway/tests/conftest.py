"""Shared test fixtures for gateway tests."""

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("IDENTITY_URL", "http://identity:8003")
os.environ.setdefault("AGENT_URL", "http://agent:8002")

from main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=True)
