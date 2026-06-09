"""FastAPI router for the agent service — analysis submission and status."""

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.api.auth import Role, TokenUser, verify_access_token
from src.infrastructure.celery_app import celery_app
from src.infrastructure.database import get_db_session
from src.infrastructure.models import AnalysisModel
from src.infrastructure.repositories import AnalysisRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter()
_bearer = HTTPBearer()

_TASK_NAME = "src.application.tasks.analyze_thesis"


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


def get_analysis_repo(
    session: AsyncSession = Depends(get_db_session),
) -> AnalysisRepository:
    return AnalysisRepository(session)


# ---------- helpers ----------


def _send_task(
    evaluation_id: str,
    text: str,
    metadata: dict[str, str],
    model: str,
    mode: str,
    review_tone: str,
    language: str,
) -> str:
    """Dispatch analyze_thesis to the Celery worker and return the task ID."""
    result = celery_app.send_task(
        _TASK_NAME,
        args=[evaluation_id, text, metadata],
        kwargs={
            "model": model,
            "mode": mode,
            "review_tone": review_tone,
            "language": language,
        },
    )
    task_id: str = str(result.id)
    logger.info(
        "analysis_task_sent",
        task_id=task_id,
        evaluation_id=evaluation_id,
        model=model,
    )
    return task_id


def _get_task_result(task_id: str) -> dict[str, Any]:
    """Return normalised status + result payload for a Celery task."""
    async_result = celery_app.AsyncResult(task_id)
    celery_status = async_result.status
    if celery_status == "SUCCESS":
        mapped = "done"
    elif celery_status in ("FAILURE", "REVOKED"):
        mapped = "error"
    else:
        mapped = "analyzing"
    result: Any = async_result.result if async_result.ready() else None
    return {"status": mapped, "result": result}


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


class AnalysisHistoryItem(BaseModel):
    id: uuid.UUID
    task_id: str | None
    evaluation_id: str
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
    repo: AnalysisRepository = Depends(get_analysis_repo),
) -> AnalysisTaskResponse:
    """Enqueue a thesis analysis and persist the task record."""
    task_id = _send_task(
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
    record = AnalysisModel(
        id=uuid.uuid4(),
        evaluation_id=body.evaluation_id,
        task_id=task_id,
        user_id=user.id,
        status="PENDING",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    await repo.save(record)
    return AnalysisTaskResponse(task_id=task_id)


@router.get("/analysis", response_model=list[AnalysisHistoryItem])
async def list_analyses(
    user: TokenUser = Depends(get_current_user),
    repo: AnalysisRepository = Depends(get_analysis_repo),
) -> list[AnalysisHistoryItem]:
    """Return the current user's analysis history."""
    records = await repo.find_by_user(user.id)
    return [
        AnalysisHistoryItem(
            id=r.id,
            task_id=r.task_id,
            evaluation_id=r.evaluation_id,
            status=r.status,
            created_at=r.created_at,
        )
        for r in records
    ]


@router.get("/analysis/{task_id}", response_model=TaskStatusResponse)
async def get_analysis_status(
    task_id: str,
    user: TokenUser = Depends(get_current_user),
    repo: AnalysisRepository = Depends(get_analysis_repo),
) -> TaskStatusResponse:
    """Poll task status — ADMIN sees any task, others only their own."""
    if user.role != Role.ADMIN:
        owned = await repo.find_by_user_and_task_id(user.id, task_id)
        if owned is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
            )

    data = _get_task_result(task_id)
    raw = data.get("result")
    result: dict[str, Any] | None = raw if isinstance(raw, dict) else None  # type: ignore[assignment]
    return TaskStatusResponse(status=str(data["status"]), result=result)
