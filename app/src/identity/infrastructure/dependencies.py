"""FastAPI dependency providers for the identity routers.

Every ``Depends(...)`` this bounded context needs, in one place, each paired
with an ``Annotated`` alias. ``get_current_user`` is also this context's one
public seam: ``mentoring`` imports it from here to answer "who is asking" —
see ``mentoring/infrastructure/dependencies.py``.
"""

from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.identity.application.auth import decode_access_token
from src.identity.application.key_check import KeyChecker
from src.identity.application.user_service import UserService
from src.identity.domain.user import Permission, User
from src.identity.infrastructure.key_checker import HttpKeyChecker
from src.identity.infrastructure.repositories import (
    AccessRequestRepository,
    ApiKeyRepository,
    LoginEventRepository,
    UserRepository,
)
from src.identity.infrastructure.token_store import RevokedTokenStore
from src.shared.database import get_db_session

_bearer = HTTPBearer()


# ---------- providers ----------


def get_token_store() -> RevokedTokenStore:
    """A fresh store per request — it holds nothing but a Redis handle.

    Named, rather than a ``Depends(lambda: ...)``: a lambda dependency cannot
    be overridden by name in tests, and every other provider in this file is
    named for exactly that reason.
    """
    return RevokedTokenStore()


# The `detail` of the 403 every endpoint but the password change gives a
# user with a temporary password. The frontend keeps them on the password
# page; this is what stops a session that skips it.
PASSWORD_CHANGE_REQUIRED = "password_change_required"  # noqa: S105 — a code


async def get_session_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    token_store: Annotated[RevokedTokenStore, Depends(get_token_store)],
) -> User:
    """FastAPI dependency — decode Bearer token and return the calling User.

    A token logged out of is refused even though its signature still holds.
    A user on a temporary password passes: only the endpoints that let them
    replace it use this directly. Everything else goes by
    ``get_current_user``.
    """
    try:
        claims = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise _unauthorized(str(exc)) from exc
    if await token_store.is_revoked(
        claims.jti, user_id=claims.user.id, issued_at=claims.issued_at
    ):
        raise _unauthorized("Token revoked")
    return claims.user


async def get_current_user(
    user: Annotated[User, Depends(get_session_user)],
) -> User:
    """FastAPI dependency — the calling User, once they have their own password.

    A temporary password from an admin opens only the password change: a
    403, not a 401, since the session itself is fine.
    """
    if user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=PASSWORD_CHANGE_REQUIRED
        )
    return user


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    """FastAPI dependency — assert MANAGE_USERS permission."""
    if not user.can(Permission.MANAGE_USERS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return user


def require_key_holder(user: Annotated[User, Depends(get_current_user)]) -> User:
    """FastAPI dependency — assert the caller keeps their own provider keys.

    A promoter, for actions; an admin, for rubrics drafted from a regulation.
    """
    if not user.can(Permission.HOLD_PROVIDER_KEYS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only users who run the model keep provider keys",
        )
    return user


def get_user_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserRepository:
    return UserRepository(session)


def get_api_key_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiKeyRepository:
    return ApiKeyRepository(session)


def get_login_event_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LoginEventRepository:
    return LoginEventRepository(session)


def get_access_request_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AccessRequestRepository:
    return AccessRequestRepository(session)


def get_user_service(
    repo: Annotated[UserRepository, Depends(get_user_repo)],
) -> UserService:
    return UserService(repo)


def get_key_checker(request: Request) -> KeyChecker:
    """Check provider keys over the process-wide HTTP client."""
    client: httpx.AsyncClient = request.app.state.http_client
    return HttpKeyChecker(client)


# ---------- Annotated aliases — what every endpoint actually types ----------

CurrentUserDep = Annotated[User, Depends(get_current_user)]
SessionUserDep = Annotated[User, Depends(get_session_user)]
AdminDep = Annotated[User, Depends(require_admin)]
UserRepoDep = Annotated[UserRepository, Depends(get_user_repo)]
ApiKeyRepoDep = Annotated[ApiKeyRepository, Depends(get_api_key_repo)]
LoginEventRepoDep = Annotated[LoginEventRepository, Depends(get_login_event_repo)]
AccessRequestRepoDep = Annotated[
    AccessRequestRepository, Depends(get_access_request_repo)
]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
TokenStoreDep = Annotated[RevokedTokenStore, Depends(get_token_store)]
KeyCheckerDep = Annotated[KeyChecker, Depends(get_key_checker)]
