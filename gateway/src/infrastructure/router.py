"""FastAPI router — auth, analysis dispatch, health, and secret-vault endpoints."""

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.auth import create_token, verify_token
from src.domain.user import Role, User
from src.infrastructure import celery_client, user_store
from src.infrastructure.database import get_db_session
from src.infrastructure.repositories import UserRepository
from src.infrastructure.secrets import get_secret_service

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter()
_bearer = HTTPBearer()


# ---------- dependencies ----------


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


def get_user_repo(
    session: AsyncSession = Depends(get_db_session),
) -> UserRepository:
    """FastAPI dependency — return a UserRepository for the current request session."""
    return UserRepository(session)


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
    thesis_type: str = "bachelor"
    author: str = ""
    title: str = ""
    year: int = 0
    field_of_study: str = ""
    model: str = "qwen3:30b-a3b"
    mode: str = "full"
    review_tone: str = "auto"


class AnalysisTaskResponse(BaseModel):
    """Response returned immediately after submitting an analysis task."""

    task_id: str


class TaskStatusResponse(BaseModel):
    """Current status and optional result of a Celery task."""

    status: str
    result: dict[str, Any] | None


class ApiKeyRequest(BaseModel):
    """Payload for storing a provider API key."""

    api_key: str
    provider: str


class ApiKeyStatusResponse(BaseModel):
    """Indicates whether an API key has been configured — never exposes the key."""

    configured: bool


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
        metadata={
            "author": body.author,
            "title": body.title,
            "year": str(body.year),
            "field_of_study": body.field_of_study,
            "thesis_type": body.thesis_type,
            "review_tone": body.review_tone,
        },
        model=body.model,
        mode=body.mode,
        review_tone=body.review_tone,
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


@router.patch("/settings/api-key", response_model=ApiKeyStatusResponse)
async def set_api_key(
    body: ApiKeyRequest,
    user: User = Depends(get_current_user),
    repo: UserRepository = Depends(get_user_repo),
) -> ApiKeyStatusResponse:
    """Encrypt and persist an AI provider API key — ADMIN only."""
    if user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    encrypted = get_secret_service().encrypt(body.api_key)
    await repo.update_api_key(user.id, encrypted)
    logger.info("api_key_stored", user_id=str(user.id), provider=body.provider)
    return ApiKeyStatusResponse(configured=True)


@router.get("/settings/api-key/status", response_model=ApiKeyStatusResponse)
async def get_api_key_status(
    user: User = Depends(get_current_user),
    repo: UserRepository = Depends(get_user_repo),
) -> ApiKeyStatusResponse:
    """Return whether the current user has an API key configured."""
    db_user = await repo.find_by_id(user.id)
    configured = db_user is not None and db_user.api_key_encrypted is not None
    return ApiKeyStatusResponse(configured=configured)
