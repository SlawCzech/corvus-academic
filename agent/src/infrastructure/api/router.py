"""FastAPI router for the agent service — dispatching and polling actions.

Status and results are read from Postgres, not from Celery's result backend:
the backend is Redis with an expiry (~1 day by default), and a promoter's
history of what the AI did for a student has to outlive that.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, cast

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.graph import IMPLEMENTED_ACTIONS
from src.domain.action import SUPPORTED_PROVIDERS, TaskStatus
from src.infrastructure.api.auth import Role, TokenUser, verify_access_token
from src.infrastructure.celery_app import celery_app
from src.infrastructure.database import get_db_session
from src.infrastructure.models import AgentTaskModel
from src.infrastructure.repositories import AgentTaskRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter()
_bearer = HTTPBearer()

_ACTION_TASK = "src.application.tasks.run_action"

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


# ---------- Annotated aliases — what every endpoint actually types ----------

CurrentUserDep = Annotated[TokenUser, Depends(get_current_user)]
TaskRepoDep = Annotated[AgentTaskRepository, Depends(get_task_repo)]


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
    model: str = "qwen3:30b-a3b"
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


# ---------- endpoints ----------


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


@router.get("/actions/{task_id}", response_model=ActionStatusResponse)
async def get_action_status(
    task_id: str,
    user: CurrentUserDep,
    repo: TaskRepoDep,
) -> ActionStatusResponse:
    """Poll one action — ADMIN sees any, others only their own."""
    record = (
        await repo.find_by_task_id(task_id)
        if user.role == Role.ADMIN
        else await repo.find_by_user_and_task_id(user.id, task_id)
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Action not found"
        )
    stored: Any = record.result
    payload = cast(dict[str, Any], stored) if isinstance(stored, dict) else {}
    return ActionStatusResponse(
        task_id=task_id,
        action_id=record.action_id,
        action_type=record.action_type,
        status=record.status,
        result=payload or None,
        error=record.error,
    )
