"""Auth endpoints — login, refresh, logout."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.identity.application.auth import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    verify_refresh_token,
)
from src.identity.infrastructure.dependencies import (
    LoginEventRepoDep,
    TokenStoreDep,
    UserServiceDep,
)
from src.identity.infrastructure.limiter import login_rate_limit
from src.identity.infrastructure.models import LoginEventModel
from src.identity.infrastructure.schemas import (
    LoginRequest,
    LoginResponse,
    RefreshResponse,
)
from src.shared.settings import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_REFRESH_COOKIE = "refresh_token"
_REFRESH_TTL = settings.refresh_token_expire_days * 24 * 3600
# How long a replaced refresh token still works. Long enough for the requests
# already on their way with it, short enough to be no use to anyone who stole it.
_REFRESH_GRACE_SECONDS = 30

# Logout must work for a caller whose token is already gone or expired, so a
# missing header is not a 403 here the way it is everywhere else.
_optional_bearer = HTTPBearer(auto_error=False)


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    svc: UserServiceDep,
    event_repo: LoginEventRepoDep,
    _rl: Annotated[None, Depends(login_rate_limit)],
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
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=_REFRESH_TTL,
        path="/auth/refresh",
    )
    logger.info("login_success", email=body.email, role=str(user.role))
    return LoginResponse(access_token=access_token)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(
    response: Response,
    svc: UserServiceDep,
    token_store: TokenStoreDep,
    refresh_token_cookie: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
) -> RefreshResponse:
    """Replace the refresh cookie and issue a new access token.

    The old refresh token is retired, not left to run out its month: logout
    revokes only the latest one, so any earlier one would outlive the session.
    """
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

    await token_store.retire(jti, _REFRESH_TTL, _REFRESH_GRACE_SECONDS)
    new_access = create_access_token(user)
    new_refresh, _new_jti = create_refresh_token(user)

    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=new_refresh,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=_REFRESH_TTL,
        path="/auth/refresh",
    )
    return RefreshResponse(access_token=new_access)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    token_store: TokenStoreDep,
    bearer: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_optional_bearer)
    ] = None,
    refresh_token_cookie: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
) -> None:
    """Revoke the access token in use and the refresh token, clear the cookie.

    Each is revoked for as long as it would otherwise still be accepted. A
    token that is missing or already invalid is skipped, not an error: the
    caller is logged out either way.
    """
    if bearer is not None:
        try:
            claims = decode_access_token(bearer.credentials)
            remaining = claims.expires_at - datetime.now(UTC)
            await token_store.revoke(claims.jti, int(remaining.total_seconds()) + 1)
        except ValueError:
            pass
    if refresh_token_cookie is not None:
        try:
            _user_id, jti = verify_refresh_token(refresh_token_cookie)
            await token_store.revoke(jti, _REFRESH_TTL)
        except ValueError:
            pass  # already invalid — still clear the cookie
    response.delete_cookie(key=_REFRESH_COOKIE, path="/auth/refresh")
