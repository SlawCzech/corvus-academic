"""FastAPI dependency providers for the identity routers.

Every ``Depends(...)`` this bounded context needs, in one place, each paired
with an ``Annotated`` alias. ``get_current_user`` is also this context's one
public seam: ``mentoring`` imports it from here to answer "who is asking" —
see ``mentoring/infrastructure/dependencies.py``.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.identity.application.auth import verify_access_token
from src.identity.application.user_service import UserService
from src.identity.domain.user import Permission, User
from src.identity.infrastructure.repositories import (
    AccessRequestRepository,
    LoginEventRepository,
    UserRepository,
)
from src.identity.infrastructure.token_store import RefreshTokenStore
from src.shared.database import get_db_session

_bearer = HTTPBearer()


# ---------- providers ----------


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
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


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    """FastAPI dependency — assert MANAGE_USERS permission."""
    if not user.can(Permission.MANAGE_USERS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return user


def get_user_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserRepository:
    return UserRepository(session)


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


def get_refresh_token_store() -> RefreshTokenStore:
    """A fresh store per request — it holds nothing but a Redis handle.

    Named, rather than the ``Depends(lambda: RefreshTokenStore())`` this
    replaces: a lambda dependency cannot be overridden by name in tests, and
    every other provider in this file is named for exactly that reason.
    """
    return RefreshTokenStore()


# ---------- Annotated aliases — what every endpoint actually types ----------

CurrentUserDep = Annotated[User, Depends(get_current_user)]
AdminDep = Annotated[User, Depends(require_admin)]
UserRepoDep = Annotated[UserRepository, Depends(get_user_repo)]
LoginEventRepoDep = Annotated[LoginEventRepository, Depends(get_login_event_repo)]
AccessRequestRepoDep = Annotated[
    AccessRequestRepository, Depends(get_access_request_repo)
]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
RefreshTokenStoreDep = Annotated[RefreshTokenStore, Depends(get_refresh_token_store)]
