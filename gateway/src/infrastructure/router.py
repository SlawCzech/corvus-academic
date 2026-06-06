"""FastAPI router — auth, analysis dispatch, health, and secret-vault endpoints."""

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.auth import (
    create_access_token,
    create_refresh_token,
    verify_access_token,
    verify_refresh_token,
)
from src.application.user_service import UserService
from src.domain.user import Role, User, UserRegistration
from src.infrastructure import celery_client
from src.infrastructure.database import get_db_session
from src.infrastructure.limiter import limiter
from src.infrastructure.models import AnalysisModel, LoginEventModel
from src.infrastructure.repositories import (
    AnalysisRepository,
    LoginEventRepository,
    UserRepository,
)
from src.infrastructure.secrets import get_secret_service
from src.infrastructure.settings import settings
from src.infrastructure.token_store import RefreshTokenStore

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter()
_bearer = HTTPBearer()

_REFRESH_COOKIE = "refresh_token"
_REFRESH_TTL = settings.refresh_token_expire_days * 24 * 3600


# ---------- dependencies ----------


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> User:
    """FastAPI dependency — decode Bearer token and return the calling User."""
    try:
        return verify_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def require_admin(user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency — assert ADMIN role."""
    if user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return user


def get_user_repo(
    session: AsyncSession = Depends(get_db_session),
) -> UserRepository:
    return UserRepository(session)


def get_analysis_repo(
    session: AsyncSession = Depends(get_db_session),
) -> AnalysisRepository:
    return AnalysisRepository(session)


def get_login_event_repo(
    session: AsyncSession = Depends(get_db_session),
) -> LoginEventRepository:
    return LoginEventRepository(session)


def get_user_service(
    repo: UserRepository = Depends(get_user_repo),
) -> UserService:
    return UserService(repo)


# ---------- schemas ----------


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105


class RegisterRequest(BaseModel):
    email: str
    password: str
    role: str = "promotor"

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = {r.value for r in Role}
        if v not in allowed:
            raise ValueError(f"role must be one of {sorted(allowed)}, got {v!r}")
        return v


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    created_at: datetime


class ChangePasswordRequest(BaseModel):
    new_password: str


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


class ApiKeyRequest(BaseModel):
    api_key: str
    provider: str


class ApiKeyStatusResponse(BaseModel):
    configured: bool


class LoginEventResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    email: str
    success: bool
    ip_address: str
    user_agent: str | None
    created_at: datetime


# ---------- auth endpoints ----------


@router.post("/auth/login", response_model=LoginResponse)
@limiter.limit("5/minute")
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    svc: UserService = Depends(get_user_service),
    event_repo: LoginEventRepository = Depends(get_login_event_repo),
) -> LoginResponse:
    """Validate credentials, set httpOnly refresh cookie, return access token."""
    user = await svc.authenticate(body.email, body.password)

    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent")
    event = LoginEventModel(
        id=uuid.uuid4(),
        user_id=user.id if user else None,
        email=body.email,
        success=user is not None,
        ip_address=ip,
        user_agent=ua,
        created_at=datetime.now(UTC),
    )
    await event_repo.save(event)

    if user is None:
        logger.warning("login_failed", email=body.email, ip=ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(user)
    refresh_token, _jti = create_refresh_token(user)

    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=_REFRESH_TTL,
        path="/auth/refresh",
    )
    logger.info("login_success", email=body.email, role=str(user.role))
    return LoginResponse(access_token=access_token)


@router.post("/auth/refresh", response_model=RefreshResponse)
async def refresh_token(
    response: Response,
    svc: UserService = Depends(get_user_service),
    token_store: RefreshTokenStore = Depends(lambda: RefreshTokenStore()),
    refresh_token_cookie: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
) -> RefreshResponse:
    """Issue a new access token using the httpOnly refresh cookie."""
    if refresh_token_cookie is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )
    try:
        user_id, jti = verify_refresh_token(refresh_token_cookie)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc

    if await token_store.is_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revoked",
        )

    user = await svc.get_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )

    new_access = create_access_token(user)
    new_refresh, _new_jti = create_refresh_token(user)

    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=new_refresh,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=_REFRESH_TTL,
        path="/auth/refresh",
    )
    return RefreshResponse(access_token=new_access)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    token_store: RefreshTokenStore = Depends(lambda: RefreshTokenStore()),
    refresh_token_cookie: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
) -> None:
    """Revoke the refresh token and clear the cookie."""
    if refresh_token_cookie is not None:
        try:
            _user_id, jti = verify_refresh_token(refresh_token_cookie)
            await token_store.revoke(jti, _REFRESH_TTL)
        except ValueError:
            pass  # already invalid — still clear the cookie
    response.delete_cookie(key=_REFRESH_COOKIE, path="/auth/refresh")


# ---------- user management endpoints ----------


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: RegisterRequest,
    _admin: User = Depends(require_admin),
    svc: UserService = Depends(get_user_service),
) -> UserResponse:
    """Register a new user — ADMIN only."""
    role = Role(body.role)
    registration = UserRegistration(
        email=body.email,
        hashed_password=UserService.hash_password(body.password),
        role=role,
    )
    try:
        user = await svc.register(registration)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return UserResponse(
        id=user.id, email=user.email, role=str(user.role), created_at=user.created_at
    )


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    _admin: User = Depends(require_admin),
    svc: UserService = Depends(get_user_service),
) -> list[UserResponse]:
    """Return all users — ADMIN only."""
    return [
        UserResponse(id=u.id, email=u.email, role=str(u.role), created_at=u.created_at)
        for u in await svc.list_all()
    ]


@router.get("/users/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)) -> UserResponse:
    """Return the current user's profile."""
    return UserResponse(
        id=user.id, email=user.email, role=str(user.role), created_at=user.created_at
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    _admin: User = Depends(require_admin),
    svc: UserService = Depends(get_user_service),
) -> None:
    """Delete a user — ADMIN only."""
    await svc.delete(user_id)


@router.patch("/users/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    svc: UserService = Depends(get_user_service),
) -> None:
    """Change the current user's password."""
    await svc.change_password(user.id, body.new_password)


# ---------- analysis endpoints ----------


@router.post(
    "/analysis",
    response_model=AnalysisTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit("10/minute")
async def submit_analysis(
    request: Request,
    body: AnalysisRequest,
    user: User = Depends(get_current_user),
    analysis_repo: AnalysisRepository = Depends(get_analysis_repo),
) -> AnalysisTaskResponse:
    """Enqueue a thesis analysis and persist the task record."""
    task_id = celery_client.send_analysis_task(
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
    await analysis_repo.save(record)
    return AnalysisTaskResponse(task_id=task_id)


@router.get("/analysis", response_model=list[AnalysisHistoryItem])
async def list_analyses(
    user: User = Depends(get_current_user),
    analysis_repo: AnalysisRepository = Depends(get_analysis_repo),
) -> list[AnalysisHistoryItem]:
    """Return the current user's analysis history."""
    records = await analysis_repo.find_by_user(user.id)
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
    user: User = Depends(get_current_user),
    analysis_repo: AnalysisRepository = Depends(get_analysis_repo),
) -> TaskStatusResponse:
    """Poll task status — ADMIN sees any task, others only their own."""
    if user.role != Role.ADMIN:
        owned = await analysis_repo.find_by_user_and_task_id(user.id, task_id)
        if owned is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
            )

    data = celery_client.get_task_result(task_id)
    raw = data.get("result")
    result: dict[str, Any] | None = raw if isinstance(raw, dict) else None  # type: ignore[assignment]
    return TaskStatusResponse(status=str(data["status"]), result=result)


# ---------- settings / secrets ----------


@router.patch("/settings/api-key", response_model=ApiKeyStatusResponse)
async def set_api_key(
    body: ApiKeyRequest,
    user: User = Depends(require_admin),
    repo: UserRepository = Depends(get_user_repo),
) -> ApiKeyStatusResponse:
    """Encrypt and persist an AI provider API key — ADMIN only."""
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


# ---------- admin endpoints ----------


@router.get("/admin/login-events", response_model=list[LoginEventResponse])
async def get_login_events(
    user_id: uuid.UUID | None = None,
    success: bool | None = None,
    _admin: User = Depends(require_admin),
    event_repo: LoginEventRepository = Depends(get_login_event_repo),
) -> list[LoginEventResponse]:
    """Return login audit events with optional filtering — ADMIN only."""
    events = await event_repo.find_all(user_id=user_id, success=success)
    return [
        LoginEventResponse(
            id=e.id,
            user_id=e.user_id,
            email=e.email,
            success=e.success,
            ip_address=e.ip_address,
            user_agent=e.user_agent,
            created_at=e.created_at,
        )
        for e in events
    ]
