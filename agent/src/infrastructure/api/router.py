"""FastAPI router for the agent service — analysis submission and status.

Status and results are read from Postgres, not from Celery's result backend:
the backend is Redis with an expiry (~1 day by default), and a promoter's
history of what the AI did for a student has to outlive that.
"""

import uuid
from datetime import UTC, datetime
from typing import Any, cast

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.graph import IMPLEMENTED_ACTIONS
from src.domain.action import ActionType, TaskStatus
from src.infrastructure.api.auth import Role, TokenUser, verify_access_token
from src.infrastructure.celery_app import celery_app
from src.infrastructure.database import get_db_session
from src.infrastructure.models import AgentTaskModel
from src.infrastructure.repositories import AgentTaskRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter()
_bearer = HTTPBearer()

_ANALYZE_TASK = "src.application.tasks.analyze_thesis"
_ACTION_TASK = "src.application.tasks.run_action"

# The frontend's own vocabulary (STATUS_LABELS in AnalysisHistoryTable, and
# the done/error checks in useAnalysis). Kept as a boundary translation so the
# stored status can stay the one the mentoring context uses.
_WIRE_STATUS: dict[str, str] = {
    TaskStatus.PENDING: "pending",
    TaskStatus.RUNNING: "processing",
    TaskStatus.COMPLETED: "done",
    TaskStatus.FAILED: "error",
}


# ---------- dependencies ----------


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
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
    session: AsyncSession = Depends(get_db_session),
) -> AgentTaskRepository:
    return AgentTaskRepository(session)


# ---------- helpers ----------


def _send_task(
    task_id: str,
    evaluation_id: str,
    text: str,
    metadata: dict[str, str],
    model: str,
    mode: str,
    review_tone: str,
    language: str,
) -> None:
    """Dispatch analyze_thesis to the Celery worker under a known task id.

    The id is chosen by the caller so the database row exists *before* the
    worker can start — otherwise a fast task could try to update a row that
    has not been written yet.
    """
    celery_app.send_task(
        _ANALYZE_TASK,
        args=[evaluation_id, text, metadata],
        kwargs={
            "model": model,
            "mode": mode,
            "review_tone": review_tone,
            "language": language,
        },
        task_id=task_id,
    )
    logger.info(
        "analysis_task_sent",
        task_id=task_id,
        evaluation_id=evaluation_id,
        model=model,
    )


def _wire_status(stored: str) -> str:
    """Translate a stored status into what the frontend expects."""
    return _WIRE_STATUS.get(stored, stored)


def _wire_result(record: AgentTaskModel) -> dict[str, Any] | None:
    """Return the stored result, or the error rendered as one."""
    stored: Any = record.result
    if isinstance(stored, dict):
        return stored  # pyright: ignore[reportUnknownVariableType]
    if record.status == TaskStatus.FAILED and record.error:
        return {"error": record.error}
    return None


# ---------- schemas ----------


_MAX_TEXT_BYTES = 2 * 1024 * 1024  # 2 MB


class AnalysisRequest(BaseModel):
    evaluation_id: str
    text: str
    thesis_type: str = "bachelor"
    author: str = ""
    title: str = ""
    year: int = 0
    field_of_study: str = ""
    model: str = "qwen3:30b-a3b"
    mode: str = "full"
    review_tone: str = "auto"
    language: str = "pl"

    @field_validator("text")
    @classmethod
    def validate_text_size(cls, v: str) -> str:
        if len(v.encode()) > _MAX_TEXT_BYTES:
            raise ValueError("text exceeds 2 MB limit")
        return v


class AnalysisTaskResponse(BaseModel):
    task_id: str


class TaskStatusResponse(BaseModel):
    status: str
    result: dict[str, Any] | None


class ActionRequest(BaseModel):
    """One AI action, with its context already assembled by `app`."""

    action_id: uuid.UUID
    action_type: str
    student_id: uuid.UUID
    context: dict[str, Any] = {}
    model: str = "qwen3:30b-a3b"
    language: str = "pl"

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


class AnalysisHistoryItem(BaseModel):
    id: uuid.UUID
    task_id: str | None
    evaluation_id: str | None
    status: str
    created_at: datetime


# ---------- endpoints ----------


@router.post(
    "/analysis",
    response_model=AnalysisTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_analysis(
    body: AnalysisRequest,
    user: TokenUser = Depends(get_current_user),
    repo: AgentTaskRepository = Depends(get_task_repo),
) -> AnalysisTaskResponse:
    """Persist a task record, then enqueue the analysis for the worker."""
    task_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    record = AgentTaskModel(
        id=uuid.uuid4(),
        task_id=task_id,
        user_id=user.id,
        action_type=ActionType.GENERATE_REVIEW,
        status=TaskStatus.PENDING,
        evaluation_id=body.evaluation_id,
        created_at=now,
        updated_at=now,
    )
    await repo.save(record)

    try:
        _send_task(
            task_id=task_id,
            evaluation_id=body.evaluation_id,
            text=body.text,
            metadata={
                "author": body.author,
                "title": body.title,
                "year": str(body.year),
                "field_of_study": body.field_of_study,
                "thesis_type": body.thesis_type,
            },
            model=body.model,
            mode=body.mode,
            review_tone=body.review_tone,
            language=body.language,
        )
    except Exception as exc:
        # A broker outage used to leave a row stuck at PENDING for good.
        logger.error("analysis_dispatch_failed", task_id=task_id, error=str(exc))
        await repo.update_status(task_id, TaskStatus.FAILED, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not queue the analysis task",
        ) from exc

    return AnalysisTaskResponse(task_id=task_id)


@router.get("/analysis", response_model=list[AnalysisHistoryItem])
async def list_analyses(
    user: TokenUser = Depends(get_current_user),
    repo: AgentTaskRepository = Depends(get_task_repo),
) -> list[AnalysisHistoryItem]:
    """Return the current user's task history."""
    records = await repo.find_by_user(user.id)
    return [
        AnalysisHistoryItem(
            id=r.id,
            task_id=r.task_id,
            evaluation_id=r.evaluation_id,
            status=_wire_status(r.status),
            created_at=r.created_at,
        )
        for r in records
    ]


@router.get("/analysis/{task_id}", response_model=TaskStatusResponse)
async def get_analysis_status(
    task_id: str,
    user: TokenUser = Depends(get_current_user),
    repo: AgentTaskRepository = Depends(get_task_repo),
) -> TaskStatusResponse:
    """Poll task status — ADMIN sees any task, others only their own."""
    record = (
        await repo.find_by_task_id(task_id)
        if user.role == Role.ADMIN
        else await repo.find_by_user_and_task_id(user.id, task_id)
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    return TaskStatusResponse(
        status=_wire_status(record.status), result=_wire_result(record)
    )


# ---------- action endpoints ----------


@router.post(
    "/actions",
    response_model=ActionTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_action(
    body: ActionRequest,
    user: TokenUser = Depends(get_current_user),
    repo: AgentTaskRepository = Depends(get_task_repo),
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

    try:
        celery_app.send_task(
            _ACTION_TASK,
            args=[
                str(body.action_id),
                body.action_type,
                str(body.student_id),
                body.context,
            ],
            kwargs={"model": body.model, "language": body.language},
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
    )
    return ActionTaskResponse(task_id=task_id)


@router.get("/actions/{task_id}", response_model=ActionStatusResponse)
async def get_action_status(
    task_id: str,
    user: TokenUser = Depends(get_current_user),
    repo: AgentTaskRepository = Depends(get_task_repo),
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
