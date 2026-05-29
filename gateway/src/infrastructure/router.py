"""FastAPI router — auth, analysis dispatch, and health endpoints."""

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from src.application.auth import create_token, verify_token
from src.domain.user import User
from src.infrastructure import celery_client, user_store

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter()
_bearer = HTTPBearer()


# ---------- dependency ----------


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> User:
    """FastAPI dependency — decode Bearer token and return the calling User."""
    try:
        return verify_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ---------- schemas ----------


class LoginRequest(BaseModel):
    """Credentials for the login endpoint."""

    email: str
    password: str


class LoginResponse(BaseModel):
    """Successful login response carrying an access token."""

    access_token: str
    token_type: str = "bearer"  # noqa: S105


class AnalysisRequest(BaseModel):
    """Payload for submitting a thesis for analysis."""

    evaluation_id: str
    text: str
    guidelines: str
    metadata: dict[str, str] = {}


class AnalysisTaskResponse(BaseModel):
    """Response returned immediately after submitting an analysis task."""

    task_id: str


class TaskStatusResponse(BaseModel):
    """Current status and optional result of a Celery task."""

    status: str
    result: dict[str, Any] | None


# ---------- endpoints ----------


@router.post("/auth/login", response_model=LoginResponse)
def login(body: LoginRequest) -> LoginResponse:
    """Validate credentials and return a JWT access token."""
    user = user_store.find_by_credentials(body.email, body.password)
    if user is None:
        logger.warning("login_failed", email=body.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_token(user)
    logger.info("login_success", email=body.email, role=str(user.role))
    return LoginResponse(access_token=token)


@router.post(
    "/analysis",
    response_model=AnalysisTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def submit_analysis(
    body: AnalysisRequest,
    _user: User = Depends(get_current_user),
) -> AnalysisTaskResponse:
    """Accept a thesis analysis request, enqueue a Celery task, and return its ID."""
    task_id = celery_client.send_analysis_task(
        evaluation_id=body.evaluation_id,
        text=body.text,
        guidelines=body.guidelines,
        metadata=body.metadata,
    )
    return AnalysisTaskResponse(task_id=task_id)


@router.get("/analysis/{task_id}", response_model=TaskStatusResponse)
def get_analysis_status(
    task_id: str,
    _user: User = Depends(get_current_user),
) -> TaskStatusResponse:
    """Poll the status and result of a previously submitted analysis task."""
    data = celery_client.get_task_result(task_id)
    raw = data.get("result")
    result: dict[str, Any] | None = raw if isinstance(raw, dict) else None  # type: ignore[assignment]
    return TaskStatusResponse(
        status=str(data["status"]),
        result=result,
    )
