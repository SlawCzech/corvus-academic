"""FastAPI router for the agent service — dispatching and polling actions.

Status and results are read from Postgres, not from Celery's result backend:
the backend is Redis with an expiry (~1 day by default), and a promoter's
history of what the AI did for a student has to outlive that.
"""

import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Annotated, Any, cast

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.graph import IMPLEMENTED_ACTIONS
from src.domain.action import SUPPORTED_PROVIDERS, TaskStatus
from src.infrastructure.api.auth import Role, TokenUser, verify_access_token
from src.infrastructure.celery_app import celery_app
from src.infrastructure.checkpoints import delete as delete_checkpoints
from src.infrastructure.database import get_db_session
from src.infrastructure.model_catalog import load_model_catalog
from src.infrastructure.models import AgentTaskModel
from src.infrastructure.repositories import AgentTaskRepository
from src.infrastructure.settings import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter()
_bearer = HTTPBearer()

_ACTION_TASK = "src.application.tasks.run_action"
_RESUME_TASK = "src.application.tasks.resume_action"

# ---------- dependencies ----------


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> TokenUser:
    """Verify Bearer token locally and return embedded user claims."""
    try:
        return verify_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_task_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentTaskRepository:
    return AgentTaskRepository(session)


async def get_http_client() -> AsyncGenerator[httpx.AsyncClient]:
    async with httpx.AsyncClient() as client:
        yield client


# ---------- Annotated aliases — what every endpoint actually types ----------

CurrentUserDep = Annotated[TokenUser, Depends(get_current_user)]
TaskRepoDep = Annotated[AgentTaskRepository, Depends(get_task_repo)]
HttpClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]


# ---------- schemas ----------


class BYOKConfig(BaseModel):
    """The caller's own provider key, decrypted by `app` for this one call.

    It is never stored here: it goes to the worker as a task argument and
    lives only as long as the graph run.
    """

    provider: str
    api_key: str

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        if v not in SUPPORTED_PROVIDERS:
            raise ValueError(
                f"provider must be one of {sorted(SUPPORTED_PROVIDERS)}, got {v!r}"
            )
        return v


class ActionRequest(BaseModel):
    """One AI action, with its context already assembled by `app`."""

    action_id: uuid.UUID
    action_type: str
    student_id: uuid.UUID
    context: dict[str, Any] = {}
    # No model named → the server's OLLAMA_MODEL, the same default /models
    # reports; `app` leaves it out when the admin has not picked one.
    model: str = Field(default_factory=lambda: settings.ollama_model)
    language: str = "pl"
    byok: BYOKConfig | None = None

    @field_validator("action_type")
    @classmethod
    def validate_action_type(cls, v: str) -> str:
        if v not in IMPLEMENTED_ACTIONS:
            raise ValueError(
                f"action_type must be one of {sorted(IMPLEMENTED_ACTIONS)}, got {v!r}"
            )
        return v


class ResumeRequest(BaseModel):
    """The promoter's answer to a paused run, and their key if they have one.

    ``decision`` is what the paused node asked for — for the review, the
    indices of the findings it may use: ``{"accepted": [0, 2, 3]}``.
    """

    decision: dict[str, Any]
    byok: BYOKConfig | None = None


class ActionTaskResponse(BaseModel):
    task_id: str


class ActionStatusResponse(BaseModel):
    """Status in the vocabulary `app` stores in mentoring.agent_actions.

    ``result`` is the task's whole payload — findings, scores and the action's
    own ``output`` key — which is what `app` persists against the action.
    """

    task_id: str
    action_id: uuid.UUID | None
    action_type: str
    status: str
    result: dict[str, Any] | None
    error: str | None
    # An `ActionErrorCode` when the promoter can act on the failure.
    error_code: str | None = None
    # {"steps": [...], "done": [...]} — the graph's nodes and those finished.
    progress: dict[str, Any] | None = None
    # Tokens spent so far, totals and by model; None when nothing reported any.
    usage: dict[str, Any] | None = None


class LocalModelResponse(BaseModel):
    name: str
    parameter_size: str | None


class ModelCatalogResponse(BaseModel):
    """What the action panel offers: local models, or the promoter's provider.

    ``byok`` maps each provider to the model a stored key runs on — the
    ``model`` field of an action does not apply to those.
    """

    backend: str
    default: str
    local: list[LocalModelResponse]
    local_available: bool
    byok: dict[str, str]


# ---------- endpoints ----------


@router.get(
    "/models",
    response_model=ModelCatalogResponse,
    dependencies=[Depends(get_current_user)],
)
async def list_models(client: HttpClientDep) -> ModelCatalogResponse:
    """The chat models installed on the Ollama the worker uses."""
    catalog = await load_model_catalog(client)
    return ModelCatalogResponse(
        backend=catalog.backend,
        default=catalog.default,
        local=[
            LocalModelResponse(name=m.name, parameter_size=m.parameter_size)
            for m in catalog.local
        ],
        local_available=catalog.local_available,
        byok=catalog.byok,
    )


@router.post(
    "/actions",
    response_model=ActionTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_action(
    body: ActionRequest,
    user: CurrentUserDep,
    repo: TaskRepoDep,
) -> ActionTaskResponse:
    """Queue one AI action for one student.

    The context arrives whole: the agent never calls `app` back mid-task, so a
    worker's job does not depend on `app` being up.
    """
    task_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    record = AgentTaskModel(
        id=uuid.uuid4(),
        task_id=task_id,
        user_id=user.id,
        action_type=body.action_type,
        status=TaskStatus.PENDING,
        action_id=body.action_id,
        student_id=body.student_id,
        created_at=now,
        updated_at=now,
    )
    await repo.save(record)

    kwargs: dict[str, Any] = {"model": body.model, "language": body.language}
    if body.byok is not None:
        # Separate task arguments, never part of the context: the context is
        # what ends up in the graph state and therefore in the stored result.
        kwargs["provider"] = body.byok.provider
        kwargs["api_key"] = body.byok.api_key

    try:
        celery_app.send_task(
            _ACTION_TASK,
            args=[
                str(body.action_id),
                body.action_type,
                str(body.student_id),
                body.context,
            ],
            kwargs=kwargs,
            task_id=task_id,
        )
    except Exception as exc:
        logger.error("action_dispatch_failed", task_id=task_id, error=str(exc))
        await repo.update_status(task_id, TaskStatus.FAILED, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not queue the action",
        ) from exc

    logger.info(
        "action_task_sent",
        task_id=task_id,
        action_id=str(body.action_id),
        action_type=body.action_type,
        student_id=str(body.student_id),
        model=body.model,
        byok_provider=body.byok.provider if body.byok else None,
    )
    return ActionTaskResponse(task_id=task_id)


async def _require_task(
    repo: AgentTaskRepository, user: TokenUser, task_id: str
) -> AgentTaskModel:
    """The caller's task — any task, for an admin — or 404."""
    record = (
        await repo.find_by_task_id(task_id)
        if user.role == Role.ADMIN
        else await repo.find_by_user_and_task_id(user.id, task_id)
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Action not found"
        )
    return record


@router.get("/actions/{task_id}", response_model=ActionStatusResponse)
async def get_action_status(
    task_id: str,
    user: CurrentUserDep,
    repo: TaskRepoDep,
) -> ActionStatusResponse:
    """Poll one action — ADMIN sees any, others only their own."""
    return _status_response(await _require_task(repo, user, task_id))


@router.post("/actions/{task_id}/resume", response_model=ActionStatusResponse)
async def resume_action(
    task_id: str,
    body: ResumeRequest,
    user: CurrentUserDep,
    repo: TaskRepoDep,
) -> ActionStatusResponse:
    """Continue a run paused for the promoter's decision.

    Queued under the paused task's own id: the checkpoint thread, the status
    row and a later cancel's revoke all keep referring to one run.
    """
    record = await _require_task(repo, user, task_id)
    if record.status != TaskStatus.AWAITING_INPUT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The action is not waiting for a decision",
        )

    kwargs: dict[str, Any] = {}
    if body.byok is not None:
        kwargs["provider"] = body.byok.provider
        kwargs["api_key"] = body.byok.api_key
    await repo.update_status(task_id, TaskStatus.PENDING)
    try:
        celery_app.send_task(
            _RESUME_TASK,
            args=[record.action_type, body.decision],
            kwargs=kwargs,
            task_id=task_id,
        )
    except Exception as exc:
        logger.error("action_resume_failed", task_id=task_id, error=str(exc))
        # Still paused: the checkpoint is intact and the promoter can retry.
        await repo.update_status(task_id, TaskStatus.AWAITING_INPUT)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not queue the action",
        ) from exc

    logger.info("action_resumed", task_id=task_id, user_id=str(user.id))
    refreshed = await repo.find_by_task_id(task_id)
    return _status_response(refreshed or record)


@router.post("/actions/{task_id}/cancel", response_model=ActionStatusResponse)
async def cancel_action(
    task_id: str,
    user: CurrentUserDep,
    repo: TaskRepoDep,
) -> ActionStatusResponse:
    """Stop an action that has not finished; a finished one is left as it is.

    The row is marked first, so the decision holds even if the revoke never
    reaches a worker. `terminate` kills a run already in progress — a model
    call is minutes of work nobody is going to read. A queued task, or one
    waiting for a retry, is dropped when a worker picks it up.
    """
    record = await _require_task(repo, user, task_id)
    if TaskStatus(record.status).is_terminal:
        return _status_response(record)

    await repo.update_status(task_id, TaskStatus.CANCELLED)
    # A run paused for the promoter keeps its state in checkpoints until it
    # is resumed; cancelled, it never will be.
    await _delete_checkpoints([record])
    try:
        celery_app.control.revoke(task_id, terminate=True)
    except Exception as exc:
        # The row already says cancelled, and a late worker write cannot
        # undo that; the run just burns its model time for nothing.
        logger.warning("action_revoke_failed", task_id=task_id, error=str(exc))
    logger.info("action_cancelled", task_id=task_id, user_id=str(user.id))
    record.status = TaskStatus.CANCELLED
    return _status_response(record)


def _revoke_unfinished(records: list[AgentTaskModel]) -> None:
    """Kill whatever of these is still queued or running; best effort."""
    for record in records:
        if record.task_id and not TaskStatus(record.status).is_terminal:
            try:
                celery_app.control.revoke(record.task_id, terminate=True)
            except Exception as exc:
                logger.warning(
                    "action_revoke_failed", task_id=record.task_id, error=str(exc)
                )


@router.delete("/actions/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_action(
    task_id: str,
    user: CurrentUserDep,
    repo: TaskRepoDep,
) -> None:
    """Forget one action: stop it if it runs, then delete its row and result.

    Idempotent — nothing to delete is not an error, so `app` can retry a
    deletion that failed on its own side after this one succeeded.
    """
    record = (
        await repo.find_by_task_id(task_id)
        if user.role == Role.ADMIN
        else await repo.find_by_user_and_task_id(user.id, task_id)
    )
    if record is None:
        return
    _revoke_unfinished([record])
    await repo.delete([record])
    await _delete_checkpoints([record])
    logger.info("action_deleted", task_id=task_id, user_id=str(user.id))


@router.delete("/students/{student_id}/actions", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student_actions(
    student_id: uuid.UUID,
    user: CurrentUserDep,
    repo: TaskRepoDep,
) -> None:
    """Forget every action run for a student `app` is deleting.

    The results here are copies of what `app` stored — reviews, findings,
    proposed topics — and a deleted student must not live on in them.
    """
    records = await repo.find_by_student(
        student_id, None if user.role == Role.ADMIN else user.id
    )
    _revoke_unfinished(records)
    await repo.delete(records)
    await _delete_checkpoints(records)
    logger.info(
        "student_actions_deleted",
        student_id=str(student_id),
        count=len(records),
        user_id=str(user.id),
    )


async def _delete_checkpoints(records: list[AgentTaskModel]) -> None:
    """Delete what a run left checkpointed — the state holds thesis text.

    A finished run deletes its own; this catches the ones that never
    finished: cancelled, or deleted while running (ADR 0009).
    """
    await asyncio.to_thread(
        delete_checkpoints, [r.task_id for r in records if r.task_id]
    )


def _status_response(record: AgentTaskModel) -> ActionStatusResponse:
    task_id = record.task_id or ""
    stored: Any = record.result
    payload = cast(dict[str, Any], stored) if isinstance(stored, dict) else {}
    raw_progress: Any = record.progress
    progress = (
        cast(dict[str, Any], raw_progress) if isinstance(raw_progress, dict) else None
    )
    raw_usage: Any = record.usage
    usage = cast(dict[str, Any], raw_usage) if isinstance(raw_usage, dict) else None
    return ActionStatusResponse(
        task_id=task_id,
        action_id=record.action_id,
        action_type=record.action_type,
        status=record.status,
        result=payload or None,
        error=record.error,
        error_code=record.error_code,
        progress=progress,
        usage=usage,
    )
