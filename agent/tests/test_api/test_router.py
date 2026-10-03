"""Integration tests for the agent HTTP API."""

import json
import os
import uuid
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
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
from src.infrastructure.api.router import get_http_client  # noqa: E402
from src.infrastructure.database import get_db_session  # noqa: E402
from src.infrastructure.models import AgentTaskModel, Base  # noqa: E402
from src.infrastructure.repositories import AgentTaskRepository  # noqa: E402
from src.infrastructure.settings import settings  # noqa: E402

_SQLITE_URL = "sqlite+aiosqlite:///:memory:"

ADMIN_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
PROMOTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
OTHER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000ff")


def _make_token(user_id: uuid.UUID, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": f"{role}@corvus.local",
        "role": role,
        "type": "access",
        "exp": int(datetime.now(UTC).timestamp()) + 3600,
    }
    # Signed with whatever secret the app verifies with — CI sets its own
    # JWT_SECRET, and a hard-coded one here only matched the local default.
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


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


_ACTION_BODY: dict[str, Any] = {
    "action_id": "aaaaaaaa-0000-0000-0000-000000000001",
    "action_type": "propose_topic",
    "student_id": "bbbbbbbb-0000-0000-0000-000000000002",
    "context": {"field_of_study": "Ekonomia", "detail": "coś ilościowego"},
}


def _submit(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post("/actions", json=_ACTION_BODY, headers=headers)
    assert resp.status_code == 202, resp.text
    return str(resp.json()["task_id"])


# ---------- health and auth ----------


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_submit_requires_auth(client: TestClient) -> None:
    assert client.post("/actions", json=_ACTION_BODY).status_code == 401


def test_status_requires_auth(client: TestClient) -> None:
    assert client.get(f"/actions/{uuid.uuid4()}").status_code == 401


def test_invalid_token_rejected(client: TestClient) -> None:
    resp = client.get(
        f"/actions/{uuid.uuid4()}", headers={"Authorization": "Bearer nonsense"}
    )
    assert resp.status_code == 401


def test_legacy_analysis_endpoints_are_gone(client: TestClient) -> None:
    """`POST /analysis` belonged to the pre-mentoring upload flow."""
    headers = _auth(PROMOTOR_ID, "promotor")
    assert client.post("/analysis", json={}, headers=headers).status_code == 404
    assert client.get("/analysis", headers=headers).status_code == 404


# ---------- dispatch ----------


def test_submit_dispatches_under_the_persisted_task_id(
    client: TestClient, dispatch: MagicMock
) -> None:
    """The row is written first, so the worker can never outrun it."""
    task_id = _submit(client, _auth(PROMOTOR_ID, "promotor"))

    dispatch.assert_called_once()
    assert dispatch.call_args.kwargs["task_id"] == task_id


def test_submit_action_sends_its_context(
    client: TestClient, dispatch: MagicMock
) -> None:
    """The context is assembled by `app` and travels with the task."""
    _submit(client, _auth(PROMOTOR_ID, "promotor"))

    sent = dispatch.call_args.kwargs["args"]
    assert sent[0] == _ACTION_BODY["action_id"]
    assert sent[1] == "propose_topic"
    assert sent[2] == _ACTION_BODY["student_id"]
    assert sent[3] == _ACTION_BODY["context"]


def test_unknown_action_type_is_rejected(
    client: TestClient, dispatch: MagicMock
) -> None:
    """An action with no graph must not be queued as work that can only fail."""
    body = {**_ACTION_BODY, "action_type": "write_the_whole_thesis"}
    resp = client.post("/actions", json=body, headers=_auth(PROMOTOR_ID, "promotor"))

    assert resp.status_code == 422
    dispatch.assert_not_called()


def test_dispatch_failure_marks_the_action_failed(
    client: TestClient, dispatch: MagicMock
) -> None:
    """A broker outage used to leave the row stuck at PENDING for good."""
    dispatch.side_effect = OSError("broker down")

    resp = client.post(
        "/actions", json=_ACTION_BODY, headers=_auth(PROMOTOR_ID, "promotor")
    )
    assert resp.status_code == 503


# ---------- polling ----------


def test_action_starts_pending(client: TestClient, dispatch: MagicMock) -> None:
    task_id = _submit(client, _auth(PROMOTOR_ID, "promotor"))

    body = client.get(
        f"/actions/{task_id}", headers=_auth(PROMOTOR_ID, "promotor")
    ).json()
    assert body["status"] == "pending"
    assert body["action_type"] == "propose_topic"
    assert body["action_id"] == _ACTION_BODY["action_id"]
    assert body["result"] is None
    # Nothing has run yet: no steps to show, nothing spent.
    assert body["progress"] is None
    assert body["usage"] is None


def test_unknown_task_is_404(client: TestClient) -> None:
    resp = client.get(
        f"/actions/{uuid.uuid4()}", headers=_auth(PROMOTOR_ID, "promotor")
    )
    assert resp.status_code == 404


def test_non_owner_gets_404(client: TestClient, dispatch: MagicMock) -> None:
    task_id = _submit(client, _auth(PROMOTOR_ID, "promotor"))

    resp = client.get(f"/actions/{task_id}", headers=_auth(OTHER_ID, "promotor"))
    assert resp.status_code == 404


def test_admin_sees_any_task(client: TestClient, dispatch: MagicMock) -> None:
    task_id = _submit(client, _auth(PROMOTOR_ID, "promotor"))

    resp = client.get(f"/actions/{task_id}", headers=_auth(ADMIN_ID, "admin"))
    assert resp.status_code == 200


# ---------- durability: the point of the status change ----------


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
            action_type=ActionType.PROPOSE_TOPIC,
            status=status,
            action_id=uuid.UUID(_ACTION_BODY["action_id"]),
            student_id=uuid.UUID(_ACTION_BODY["student_id"]),
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
    payload = {"output": {"topics": [{"title": "Instytucje a wzrost"}]}}
    await _store(db_session, task_id, TaskStatus.COMPLETED, result=payload)

    resp = client.get(f"/actions/{task_id}", headers=_auth(PROMOTOR_ID, "promotor"))

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["result"]["output"]["topics"][0]["title"] == "Instytucje a wzrost"


async def test_status_reports_the_tokens_spent(
    client: TestClient, db_session: AsyncSession, dispatch: MagicMock
) -> None:
    task_id = str(uuid.uuid4())
    await _store(db_session, task_id, TaskStatus.COMPLETED, result={"output": {}})
    usage = {
        "input_tokens": 900,
        "output_tokens": 100,
        "total_tokens": 1000,
        "by_model": {
            "claude-sonnet-5-5": {
                "input_tokens": 900,
                "output_tokens": 100,
                "total_tokens": 1000,
            }
        },
    }
    await AgentTaskRepository(db_session).add_usage(task_id, usage)  # type: ignore[arg-type]

    resp = client.get(f"/actions/{task_id}", headers=_auth(PROMOTOR_ID, "promotor"))

    assert resp.json()["usage"] == usage


async def test_failed_task_reports_its_error(
    client: TestClient, db_session: AsyncSession, dispatch: MagicMock
) -> None:
    task_id = str(uuid.uuid4())
    await _store(db_session, task_id, TaskStatus.FAILED, error="Ollama unreachable")

    resp = client.get(f"/actions/{task_id}", headers=_auth(PROMOTOR_ID, "promotor"))

    assert resp.json()["status"] == "failed"
    assert resp.json()["error"] == "Ollama unreachable"


async def test_running_task_is_reported_as_running(
    client: TestClient, db_session: AsyncSession, dispatch: MagicMock
) -> None:
    task_id = str(uuid.uuid4())
    await _store(db_session, task_id, TaskStatus.RUNNING)

    resp = client.get(f"/actions/{task_id}", headers=_auth(PROMOTOR_ID, "promotor"))

    assert resp.json()["status"] == "running"
    assert resp.json()["result"] is None


# ---------- cancelling ----------


@pytest.fixture
def revoke() -> Generator[MagicMock, None, None]:
    with patch("src.infrastructure.api.router.celery_app.control.revoke") as mock:
        yield mock


async def test_cancel_stops_a_running_task(
    client: TestClient, db_session: AsyncSession, revoke: MagicMock
) -> None:
    task_id = str(uuid.uuid4())
    await _store(db_session, task_id, TaskStatus.RUNNING)

    resp = client.post(
        f"/actions/{task_id}/cancel", headers=_auth(PROMOTOR_ID, "promotor")
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"
    revoke.assert_called_once_with(task_id, terminate=True)
    polled = client.get(f"/actions/{task_id}", headers=_auth(PROMOTOR_ID, "promotor"))
    assert polled.json()["status"] == "cancelled"


async def test_cancel_leaves_a_finished_task_alone(
    client: TestClient, db_session: AsyncSession, revoke: MagicMock
) -> None:
    task_id = str(uuid.uuid4())
    await _store(db_session, task_id, TaskStatus.COMPLETED, result={"summary": "x"})

    resp = client.post(
        f"/actions/{task_id}/cancel", headers=_auth(PROMOTOR_ID, "promotor")
    )

    assert resp.json()["status"] == "completed"
    revoke.assert_not_called()


async def test_cancel_holds_when_the_revoke_fails(
    client: TestClient, db_session: AsyncSession, revoke: MagicMock
) -> None:
    """The broker being down must not leave the task looking alive."""
    revoke.side_effect = ConnectionError("redis down")
    task_id = str(uuid.uuid4())
    await _store(db_session, task_id, TaskStatus.PENDING)

    resp = client.post(
        f"/actions/{task_id}/cancel", headers=_auth(PROMOTOR_ID, "promotor")
    )

    assert resp.json()["status"] == "cancelled"


async def test_cancel_someone_elses_task_is_404(
    client: TestClient, db_session: AsyncSession, revoke: MagicMock
) -> None:
    task_id = str(uuid.uuid4())
    await _store(db_session, task_id, TaskStatus.RUNNING)

    resp = client.post(
        f"/actions/{task_id}/cancel", headers=_auth(uuid.uuid4(), "promotor")
    )

    assert resp.status_code == 404
    revoke.assert_not_called()


# ---------- deleting ----------


async def test_delete_forgets_a_finished_action(
    client: TestClient, db_session: AsyncSession, revoke: MagicMock
) -> None:
    task_id = str(uuid.uuid4())
    await _store(db_session, task_id, TaskStatus.COMPLETED, result={"summary": "x"})
    headers = _auth(PROMOTOR_ID, "promotor")

    resp = client.delete(f"/actions/{task_id}", headers=headers)

    assert resp.status_code == 204
    assert client.get(f"/actions/{task_id}", headers=headers).status_code == 404
    revoke.assert_not_called()


async def test_delete_stops_a_running_action_first(
    client: TestClient, db_session: AsyncSession, revoke: MagicMock
) -> None:
    task_id = str(uuid.uuid4())
    await _store(db_session, task_id, TaskStatus.RUNNING)

    client.delete(f"/actions/{task_id}", headers=_auth(PROMOTOR_ID, "promotor"))

    revoke.assert_called_once_with(task_id, terminate=True)


async def test_delete_takes_the_runs_checkpoints_too(
    client: TestClient, db_session: AsyncSession, revoke: MagicMock
) -> None:
    """A run that never finished leaves checkpoints — with the thesis in them."""
    task_id = str(uuid.uuid4())
    await _store(db_session, task_id, TaskStatus.CANCELLED)

    with patch("src.infrastructure.api.router.delete_checkpoints") as delete:
        client.delete(f"/actions/{task_id}", headers=_auth(PROMOTOR_ID, "promotor"))

    delete.assert_called_once_with([task_id])


def test_delete_of_nothing_is_not_an_error(client: TestClient) -> None:
    """`app` retries a deletion that failed on its side after this one succeeded."""
    resp = client.delete(
        f"/actions/{uuid.uuid4()}", headers=_auth(PROMOTOR_ID, "promotor")
    )
    assert resp.status_code == 204


async def test_delete_leaves_someone_elses_action(
    client: TestClient, db_session: AsyncSession, revoke: MagicMock
) -> None:
    task_id = str(uuid.uuid4())
    await _store(db_session, task_id, TaskStatus.COMPLETED)

    client.delete(f"/actions/{task_id}", headers=_auth(uuid.uuid4(), "promotor"))

    kept = client.get(f"/actions/{task_id}", headers=_auth(PROMOTOR_ID, "promotor"))
    assert kept.status_code == 200


async def test_deleting_a_students_actions_takes_every_result(
    client: TestClient, db_session: AsyncSession, revoke: MagicMock
) -> None:
    done, running = str(uuid.uuid4()), str(uuid.uuid4())
    await _store(db_session, done, TaskStatus.COMPLETED, result={"summary": "x"})
    await _store(db_session, running, TaskStatus.RUNNING)
    headers = _auth(PROMOTOR_ID, "promotor")

    with patch("src.infrastructure.api.router.delete_checkpoints") as checkpoints:
        resp = client.delete(
            f"/students/{_ACTION_BODY['student_id']}/actions", headers=headers
        )

    assert resp.status_code == 204
    assert client.get(f"/actions/{done}", headers=headers).status_code == 404
    assert client.get(f"/actions/{running}", headers=headers).status_code == 404
    revoke.assert_called_once_with(running, terminate=True)
    assert sorted(checkpoints.call_args.args[0]) == sorted([done, running])


async def test_deleting_a_students_actions_leaves_other_promoters_alone(
    client: TestClient, db_session: AsyncSession, revoke: MagicMock
) -> None:
    task_id = str(uuid.uuid4())
    await _store(db_session, task_id, TaskStatus.COMPLETED)

    client.delete(
        f"/students/{_ACTION_BODY['student_id']}/actions",
        headers=_auth(uuid.uuid4(), "promotor"),
    )

    kept = client.get(f"/actions/{task_id}", headers=_auth(PROMOTOR_ID, "promotor"))
    assert kept.status_code == 200


# ---------- the caller's own key ----------


def test_byok_travels_as_task_arguments_not_context(
    client: TestClient, dispatch: MagicMock
) -> None:
    """The context ends up in the state, and the state ends up stored."""
    body = {
        **_ACTION_BODY,
        "byok": {"provider": "claude", "api_key": "sk-user-key"},
    }
    resp = client.post("/actions", json=body, headers=_auth(PROMOTOR_ID, "promotor"))
    assert resp.status_code == 202

    call = dispatch.call_args.kwargs
    assert call["kwargs"]["provider"] == "claude"
    assert call["kwargs"]["api_key"] == "sk-user-key"
    assert "sk-user-key" not in json.dumps(call["args"])


def test_action_without_byok_sends_no_credentials(
    client: TestClient, dispatch: MagicMock
) -> None:
    _submit(client, _auth(PROMOTOR_ID, "promotor"))

    assert "api_key" not in dispatch.call_args.kwargs["kwargs"]


def test_unsupported_provider_is_rejected(
    client: TestClient, dispatch: MagicMock
) -> None:
    body = {**_ACTION_BODY, "byok": {"provider": "deepmind", "api_key": "k"}}
    resp = client.post("/actions", json=body, headers=_auth(PROMOTOR_ID, "promotor"))

    assert resp.status_code == 422
    dispatch.assert_not_called()


async def test_the_key_is_not_stored_on_the_task_row(
    client: TestClient, db_session: AsyncSession, dispatch: MagicMock
) -> None:
    body = {
        **_ACTION_BODY,
        "byok": {"provider": "claude", "api_key": "sk-user-key"},
    }
    task_id = client.post(
        "/actions", json=body, headers=_auth(PROMOTOR_ID, "promotor")
    ).json()["task_id"]

    stored = await AgentTaskRepository(db_session).find_by_task_id(task_id)
    assert stored is not None
    assert "sk-user-key" not in json.dumps(
        {"result": stored.result, "error": stored.error}, default=str
    )


# ---------- GET /models ----------


def test_models_requires_a_token(client: TestClient) -> None:
    assert client.get("/models").status_code in (401, 403)


def test_models_lists_ollama_chat_models(client: TestClient) -> None:
    tags = {"models": [{"name": "gemma4:12b", "details": {"family": "gemma4"}}]}

    async def _fake_client() -> AsyncGenerator[httpx.AsyncClient, None]:
        transport = httpx.MockTransport(lambda _req: httpx.Response(200, json=tags))
        async with httpx.AsyncClient(transport=transport) as fake:
            yield fake

    app.dependency_overrides[get_http_client] = _fake_client
    try:
        resp = client.get("/models", headers=_auth(PROMOTOR_ID, "promotor"))
    finally:
        app.dependency_overrides.pop(get_http_client, None)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["local"] == [{"name": "gemma4:12b", "parameter_size": None}]
    assert body["local_available"] is True
    assert body["default"] == settings.ollama_model


# ---------- resuming a paused run ----------


async def test_resume_queues_the_decision_under_the_same_task_id(
    client: TestClient, db_session: AsyncSession, dispatch: MagicMock
) -> None:
    task_id = str(uuid.uuid4())
    await _store(db_session, task_id, TaskStatus.AWAITING_INPUT, result={"x": 1})

    resp = client.post(
        f"/actions/{task_id}/resume",
        json={
            "decision": {"accepted": [0, 2]},
            "byok": {"provider": "claude", "api_key": "sk-user"},
        },
        headers=_auth(PROMOTOR_ID, "promotor"),
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"
    sent = dispatch.call_args
    assert sent.args[0] == "src.application.tasks.resume_action"
    assert sent.kwargs["task_id"] == task_id
    assert sent.kwargs["args"] == [ActionType.PROPOSE_TOPIC, {"accepted": [0, 2]}]
    assert sent.kwargs["kwargs"] == {"provider": "claude", "api_key": "sk-user"}


async def test_resume_of_a_run_that_is_not_paused_is_409(
    client: TestClient, db_session: AsyncSession, dispatch: MagicMock
) -> None:
    task_id = str(uuid.uuid4())
    await _store(db_session, task_id, TaskStatus.RUNNING)

    resp = client.post(
        f"/actions/{task_id}/resume",
        json={"decision": {"accepted": []}},
        headers=_auth(PROMOTOR_ID, "promotor"),
    )

    assert resp.status_code == 409
    dispatch.assert_not_called()


async def test_resume_that_cannot_be_queued_stays_paused(
    client: TestClient, db_session: AsyncSession, dispatch: MagicMock
) -> None:
    task_id = str(uuid.uuid4())
    await _store(db_session, task_id, TaskStatus.AWAITING_INPUT)
    dispatch.side_effect = OSError("broker down")
    headers = _auth(PROMOTOR_ID, "promotor")

    resp = client.post(
        f"/actions/{task_id}/resume", json={"decision": {}}, headers=headers
    )

    assert resp.status_code == 503
    body = client.get(f"/actions/{task_id}", headers=headers).json()
    assert body["status"] == "awaiting_input"


async def test_cancelling_a_paused_run_deletes_its_checkpoints(
    client: TestClient, db_session: AsyncSession, revoke: MagicMock
) -> None:
    task_id = str(uuid.uuid4())
    await _store(db_session, task_id, TaskStatus.AWAITING_INPUT)

    with patch("src.infrastructure.api.router.delete_checkpoints") as delete:
        resp = client.post(
            f"/actions/{task_id}/cancel", headers=_auth(PROMOTOR_ID, "promotor")
        )

    assert resp.json()["status"] == "cancelled"
    delete.assert_called_once_with([task_id])
