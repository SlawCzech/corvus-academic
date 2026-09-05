"""Integration tests for agent HTTP API endpoints."""

import os
import uuid
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/thesis_reviewer"
)
os.environ.setdefault("JWT_SECRET", "test-secret-key-that-is-long-enough-32ch")

from main import app  # noqa: E402
from src.domain.action import ActionType, TaskStatus  # noqa: E402
from src.infrastructure.database import get_db_session  # noqa: E402
from src.infrastructure.models import AgentTaskModel, Base  # noqa: E402
from src.infrastructure.repositories import AgentTaskRepository  # noqa: E402

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


def _auth(user_id: uuid.UUID, role: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_token(user_id, role)}"}


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
def client(db_session: AsyncSession) -> Generator[TestClient, None, None]:
    async def _override() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override
    tc = TestClient(app)
    yield tc
    app.dependency_overrides.pop(get_db_session, None)


@pytest.fixture
def dispatch() -> Generator[MagicMock, None, None]:
    """Capture Celery dispatch, and fail loudly if the result backend is read.

    Reading status back from Celery is exactly the behaviour this service
    moved away from — the backend expires, the database does not.
    """

    def _no_backend(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("status must come from Postgres, not Celery")

    with (
        patch("src.infrastructure.api.router.celery_app.send_task") as send,
        patch(
            "src.infrastructure.api.router.celery_app.AsyncResult",
            side_effect=_no_backend,
        ),
    ):
        yield send


_ANALYSIS_BODY: dict[str, Any] = {
    "evaluation_id": "550e8400-e29b-41d4-a716-446655440000",
    "text": "Chapter 1: Introduction.",
    "thesis_type": "bachelor",
}


def _submit(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post("/analysis", json=_ANALYSIS_BODY, headers=headers)
    assert resp.status_code == 202, resp.text
    return str(resp.json()["task_id"])


# ---------- health and auth ----------


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_submit_requires_auth(client: TestClient) -> None:
    assert client.post("/analysis", json=_ANALYSIS_BODY).status_code == 401


def test_list_requires_auth(client: TestClient) -> None:
    assert client.get("/analysis").status_code == 401


def test_status_requires_auth(client: TestClient) -> None:
    assert client.get(f"/analysis/{uuid.uuid4()}").status_code == 401


def test_invalid_token_rejected(client: TestClient) -> None:
    resp = client.get("/analysis", headers={"Authorization": "Bearer nonsense"})
    assert resp.status_code == 401


# ---------- submit ----------


def test_submit_dispatches_under_the_persisted_task_id(
    client: TestClient, dispatch: MagicMock
) -> None:
    """The row is written first, so the worker can never outrun it."""
    task_id = _submit(client, _auth(PROMOTOR_ID, "promotor"))

    dispatch.assert_called_once()
    assert dispatch.call_args.kwargs["task_id"] == task_id


def test_submitted_task_starts_pending(
    client: TestClient, dispatch: MagicMock
) -> None:
    task_id = _submit(client, _auth(PROMOTOR_ID, "promotor"))

    resp = client.get(f"/analysis/{task_id}", headers=_auth(PROMOTOR_ID, "promotor"))
    assert resp.status_code == 200
    assert resp.json() == {"status": "pending", "result": None}


def test_dispatch_failure_marks_the_task_failed(
    client: TestClient, dispatch: MagicMock
) -> None:
    """A broker outage used to leave the row stuck at PENDING for good."""
    dispatch.side_effect = OSError("broker down")

    resp = client.post(
        "/analysis", json=_ANALYSIS_BODY, headers=_auth(PROMOTOR_ID, "promotor")
    )
    assert resp.status_code == 503

    history = client.get("/analysis", headers=_auth(PROMOTOR_ID, "promotor")).json()
    assert [h["status"] for h in history] == ["error"]


# ---------- history ----------


def test_list_analyses_empty(client: TestClient) -> None:
    resp = client.get("/analysis", headers=_auth(PROMOTOR_ID, "promotor"))
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_analyses_after_submit(
    client: TestClient, dispatch: MagicMock
) -> None:
    task_id = _submit(client, _auth(PROMOTOR_ID, "promotor"))

    body = client.get("/analysis", headers=_auth(PROMOTOR_ID, "promotor")).json()
    assert len(body) == 1
    assert body[0]["task_id"] == task_id
    assert body[0]["evaluation_id"] == _ANALYSIS_BODY["evaluation_id"]
    assert body[0]["status"] == "pending"


def test_history_is_scoped_to_the_caller(
    client: TestClient, dispatch: MagicMock
) -> None:
    _submit(client, _auth(PROMOTOR_ID, "promotor"))

    other = uuid.UUID("00000000-0000-0000-0000-0000000000ff")
    assert client.get("/analysis", headers=_auth(other, "promotor")).json() == []


# ---------- status ----------


def test_unknown_task_is_404(client: TestClient) -> None:
    resp = client.get(
        f"/analysis/{uuid.uuid4()}", headers=_auth(PROMOTOR_ID, "promotor")
    )
    assert resp.status_code == 404


def test_non_owner_gets_404(client: TestClient, dispatch: MagicMock) -> None:
    task_id = _submit(client, _auth(PROMOTOR_ID, "promotor"))

    other = uuid.UUID("00000000-0000-0000-0000-0000000000ff")
    resp = client.get(f"/analysis/{task_id}", headers=_auth(other, "promotor"))
    assert resp.status_code == 404


def test_admin_sees_any_task(client: TestClient, dispatch: MagicMock) -> None:
    task_id = _submit(client, _auth(PROMOTOR_ID, "promotor"))

    resp = client.get(f"/analysis/{task_id}", headers=_auth(ADMIN_ID, "admin"))
    assert resp.status_code == 200


# ---------- durability: the point of the whole change ----------


async def _store(
    session: AsyncSession,
    task_id: str,
    status: TaskStatus,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    """Write a finished task the way the Celery worker would."""
    repo = AgentTaskRepository(session)
    now = datetime.now(UTC)
    await repo.save(
        AgentTaskModel(
            id=uuid.uuid4(),
            task_id=task_id,
            user_id=PROMOTOR_ID,
            action_type=ActionType.GENERATE_REVIEW,
            status=status,
            evaluation_id="550e8400-e29b-41d4-a716-446655440000",
            result=result,
            error=error,
            created_at=now,
            updated_at=now,
        )
    )


async def test_completed_result_survives_without_celery(
    client: TestClient, db_session: AsyncSession, dispatch: MagicMock
) -> None:
    """Status and result come from Postgres — Redis may have long expired."""
    task_id = str(uuid.uuid4())
    payload = {"findings": [], "scores": [], "summary": "Praca spełnia wymogi."}
    await _store(db_session, task_id, TaskStatus.COMPLETED, result=payload)

    resp = client.get(f"/analysis/{task_id}", headers=_auth(PROMOTOR_ID, "promotor"))

    assert resp.status_code == 200
    assert resp.json()["status"] == "done"
    assert resp.json()["result"]["summary"] == "Praca spełnia wymogi."


async def test_failed_task_reports_its_error(
    client: TestClient, db_session: AsyncSession, dispatch: MagicMock
) -> None:
    task_id = str(uuid.uuid4())
    await _store(db_session, task_id, TaskStatus.FAILED, error="Ollama unreachable")

    resp = client.get(f"/analysis/{task_id}", headers=_auth(PROMOTOR_ID, "promotor"))

    assert resp.status_code == 200
    assert resp.json()["status"] == "error"
    assert resp.json()["result"] == {"error": "Ollama unreachable"}


async def test_running_task_is_reported_as_processing(
    client: TestClient, db_session: AsyncSession, dispatch: MagicMock
) -> None:
    task_id = str(uuid.uuid4())
    await _store(db_session, task_id, TaskStatus.RUNNING)

    resp = client.get(f"/analysis/{task_id}", headers=_auth(PROMOTOR_ID, "promotor"))

    assert resp.json() == {"status": "processing", "result": None}


# ---------- actions ----------


_ACTION_BODY: dict[str, Any] = {
    "action_id": "aaaaaaaa-0000-0000-0000-000000000001",
    "action_type": "propose_topic",
    "student_id": "bbbbbbbb-0000-0000-0000-000000000002",
    "context": {"field_of_study": "Ekonomia", "detail": "coś ilościowego"},
}


def _submit_action(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post("/actions", json=_ACTION_BODY, headers=headers)
    assert resp.status_code == 202, resp.text
    return str(resp.json()["task_id"])


def test_submit_action_requires_auth(client: TestClient) -> None:
    assert client.post("/actions", json=_ACTION_BODY).status_code == 401


def test_submit_action_dispatches_with_its_context(
    client: TestClient, dispatch: MagicMock
) -> None:
    """The context is assembled by `app` and travels with the task."""
    task_id = _submit_action(client, _auth(PROMOTOR_ID, "promotor"))

    sent = dispatch.call_args.kwargs["args"]
    assert dispatch.call_args.kwargs["task_id"] == task_id
    assert sent[0] == _ACTION_BODY["action_id"]
    assert sent[1] == "propose_topic"
    assert sent[2] == _ACTION_BODY["student_id"]
    assert sent[3] == _ACTION_BODY["context"]


def test_unimplemented_action_type_is_rejected(
    client: TestClient, dispatch: MagicMock
) -> None:
    """Phase 3 actions must not be queued as work that can only fail."""
    body = {**_ACTION_BODY, "action_type": "check_progress"}
    resp = client.post("/actions", json=body, headers=_auth(PROMOTOR_ID, "promotor"))

    assert resp.status_code == 422
    dispatch.assert_not_called()


def test_action_starts_pending(client: TestClient, dispatch: MagicMock) -> None:
    task_id = _submit_action(client, _auth(PROMOTOR_ID, "promotor"))

    resp = client.get(f"/actions/{task_id}", headers=_auth(PROMOTOR_ID, "promotor"))
    body = resp.json()
    assert body["status"] == "pending"
    assert body["action_type"] == "propose_topic"
    assert body["action_id"] == _ACTION_BODY["action_id"]
    assert body["result"] is None


def test_action_of_another_promotor_is_404(
    client: TestClient, dispatch: MagicMock
) -> None:
    task_id = _submit_action(client, _auth(PROMOTOR_ID, "promotor"))

    other = uuid.UUID("00000000-0000-0000-0000-0000000000ff")
    resp = client.get(f"/actions/{task_id}", headers=_auth(other, "promotor"))
    assert resp.status_code == 404


def test_unknown_action_is_404(client: TestClient) -> None:
    resp = client.get(
        f"/actions/{uuid.uuid4()}", headers=_auth(PROMOTOR_ID, "promotor")
    )
    assert resp.status_code == 404


async def test_completed_action_returns_its_payload(
    client: TestClient, db_session: AsyncSession, dispatch: MagicMock
) -> None:
    """Same durability as the legacy endpoint: the row is the source of truth."""
    task_id = str(uuid.uuid4())
    payload = {"output": {"topics": [{"title": "Instytucje a wzrost"}]}}
    repo = AgentTaskRepository(db_session)
    now = datetime.now(UTC)
    await repo.save(
        AgentTaskModel(
            id=uuid.uuid4(),
            task_id=task_id,
            user_id=PROMOTOR_ID,
            action_type=ActionType.PROPOSE_TOPIC,
            status=TaskStatus.COMPLETED,
            action_id=uuid.UUID(_ACTION_BODY["action_id"]),
            student_id=uuid.UUID(_ACTION_BODY["student_id"]),
            result=payload,
            created_at=now,
            updated_at=now,
        )
    )

    resp = client.get(f"/actions/{task_id}", headers=_auth(PROMOTOR_ID, "promotor"))

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["result"]["output"]["topics"][0]["title"] == "Instytucje a wzrost"
