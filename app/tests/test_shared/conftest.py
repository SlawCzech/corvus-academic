"""Fixtures for cross-cutting app tests.

Environment defaults live in the parent `tests/conftest.py`.
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """A client with the app's lifespan run, so `http_client` exists."""
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
