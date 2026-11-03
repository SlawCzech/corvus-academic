"""The rate limiter against a real router, not the no-op the other tests use."""

from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from src.identity.infrastructure.limiter import RateLimit


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _client(limit: int, clock: Clock | None = None) -> TestClient:
    limiter = RateLimit(limit=limit, window_seconds=60, clock=clock or Clock())
    # Included, as every router in `main.py` is: FastAPI 0.162 lists an
    # included router without a `path`, which broke fastapi-limiter.
    router = APIRouter(prefix="/auth")

    @router.post("/login")
    async def login(_rl: Annotated[None, Depends(limiter)]) -> dict[str, bool]:
        return {"ok": True}

    @router.post("/other")
    async def other(_rl: Annotated[None, Depends(limiter)]) -> dict[str, bool]:
        return {"ok": True}

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_requests_within_the_limit_pass() -> None:
    client = _client(limit=2)
    assert [client.post("/auth/login").status_code for _ in range(2)] == [200, 200]


def test_the_request_past_the_limit_is_429() -> None:
    client = _client(limit=2)
    codes = [client.post("/auth/login").status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_each_path_has_its_own_count() -> None:
    client = _client(limit=1)
    assert client.post("/auth/login").status_code == 200
    assert client.post("/auth/other").status_code == 200


def test_each_client_has_its_own_count() -> None:
    """fastapi-limiter's memory backend counted the whole world as one."""
    client = _client(limit=1)
    first = client.post("/auth/login", headers={"X-Forwarded-For": "10.0.0.1"})
    second = client.post("/auth/login", headers={"X-Forwarded-For": "10.0.0.2"})
    assert (first.status_code, second.status_code) == (200, 200)


def test_the_window_slides() -> None:
    clock = Clock()
    client = _client(limit=1, clock=clock)
    assert client.post("/auth/login").status_code == 200
    clock.now += 59
    assert client.post("/auth/login").status_code == 429
    clock.now += 1
    assert client.post("/auth/login").status_code == 200
