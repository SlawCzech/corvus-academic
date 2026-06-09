"""Integration tests for agent HTTP API endpoints."""

import os
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/thesis_reviewer")
os.environ.setdefault("JWT_SECRET", "test-secret-key-that-is-long-enough-32ch")

from main import app  # noqa: E402
from src.infrastructure.database import get_db_session  # noqa: E402
from src.infrastructure.models import Base  # noqa: E402

_SQLITE_URL = "sqlite+aiosqlite:///:memory:"
_JWT_SECRET = "test-secret-key-that-is-long-enough-32ch"

ADMIN_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
PROMOTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


def _make_token(user_id: uuid.UUID, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": f"{role}@corvus.local",
        "role": role,
        "type": "access",
        "exp": int(datetime.now(UTC).timestamp()) + 3600,
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm="HS256")


_SCHEMA_TRANSLATE = {"schema_translate_map": {"analysis": None}}


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(_SQLITE_URL, execution_options=_SCHEMA_TRANSLATE)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def client(db_session: AsyncSession) -> TestClient:
    async def _override() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override
    tc = TestClient(app)
    yield tc
    app.dependency_overrides.pop(get_db_session, None)


@pytest.fixture
def fake_task_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def mock_celery(fake_task_id: str) -> MagicMock:
    mock_result = MagicMock()
    mock_result.id = fake_task_id
    mock_result.status = "PENDING"
    mock_result.ready.return_value = False
    mock_result.result = None

    def _send_task(*args: Any, **kwargs: Any) -> MagicMock:
        return mock_result

    def _async_result(tid: str) -> MagicMock:
        r = MagicMock()
        r.id = tid
        r.status = "SUCCESS"
        r.ready.return_value = True
        r.result = {"score": 85}
        return r

    with patch("src.infrastructure.api.router.celery_app.send_task", side_effect=_send_task), \
         patch("src.infrastructure.api.router.celery_app.AsyncResult", side_effect=_async_result):
        yield mock_result


# ---------- health ----------


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------- auth guards ----------


def test_submit_requires_auth(client: TestClient) -> None:
    resp = client.post("/analysis", json={"evaluation_id": "e1", "text": "t"})
    assert resp.status_code in (401, 403)


def test_list_requires_auth(client: TestClient) -> None:
    resp = client.get("/analysis")
    assert resp.status_code in (401, 403)


def test_status_requires_auth(client: TestClient) -> None:
    resp = client.get(f"/analysis/{uuid.uuid4()}")
    assert resp.status_code in (401, 403)


def test_invalid_token_rejected(client: TestClient) -> None:
    headers = {"Authorization": "Bearer not.a.valid.token"}
    resp = client.post("/analysis", json={"evaluation_id": "e1", "text": "t"}, headers=headers)
    assert resp.status_code == 401


# ---------- submit analysis ----------


def test_submit_analysis_success(client: TestClient, mock_celery: MagicMock, fake_task_id: str) -> None:
    token = _make_token(PROMOTOR_ID, "promotor")
    resp = client.post(
        "/analysis",
        json={"evaluation_id": str(uuid.uuid4()), "text": "thesis content"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 202
    body: dict[str, Any] = resp.json()
    assert "task_id" in body
    assert body["task_id"] == fake_task_id


# ---------- list analyses ----------


def test_list_analyses_empty(client: TestClient) -> None:
    token = _make_token(PROMOTOR_ID, "promotor")
    resp = client.get("/analysis", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_analyses_after_submit(
    client: TestClient, mock_celery: MagicMock
) -> None:
    token = _make_token(ADMIN_ID, "admin")
    client.post(
        "/analysis",
        json={"evaluation_id": "e1", "text": "t"},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = client.get("/analysis", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ---------- task status ----------


def test_admin_sees_any_task(client: TestClient, mock_celery: MagicMock, fake_task_id: str) -> None:
    token = _make_token(ADMIN_ID, "admin")
    resp = client.get(f"/analysis/{fake_task_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body: dict[str, Any] = resp.json()
    assert body["status"] == "done"
    assert body["result"] == {"score": 85}


def test_owner_can_see_own_task(client: TestClient, mock_celery: MagicMock, fake_task_id: str) -> None:
    token = _make_token(PROMOTOR_ID, "promotor")
    submit = client.post(
        "/analysis",
        json={"evaluation_id": "e1", "text": "t"},
        headers={"Authorization": f"Bearer {token}"},
    )
    task_id = submit.json()["task_id"]
    resp = client.get(f"/analysis/{task_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_non_owner_gets_404(client: TestClient, mock_celery: MagicMock, fake_task_id: str) -> None:
    admin_token = _make_token(ADMIN_ID, "admin")
    client.post(
        "/analysis",
        json={"evaluation_id": "e1", "text": "t"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    promotor_token = _make_token(PROMOTOR_ID, "promotor")
    resp = client.get(f"/analysis/{fake_task_id}", headers={"Authorization": f"Bearer {promotor_token}"})
    assert resp.status_code == 404
