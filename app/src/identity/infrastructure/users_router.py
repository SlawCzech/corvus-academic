"""User management endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from src.identity.application.user_service import UserService, WrongPasswordError
from src.identity.domain.user import Role, UserRegistration
from src.identity.infrastructure.dependencies import (
    AdminDep,
    CurrentUserDep,
    TokenStoreDep,
    UserServiceDep,
)
from src.identity.infrastructure.limiter import login_rate_limit
from src.identity.infrastructure.schemas import (
    ChangePasswordRequest,
    LoginResponse,
    RegisterRequest,
    UserResponse,
    UserSettings,
    user_response,
)
from src.identity.infrastructure.session import REFRESH_TTL, start_session

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: RegisterRequest,
    _admin: AdminDep,
    svc: UserServiceDep,
) -> UserResponse:
    """Register a new user — ADMIN only."""
    role = Role(body.role)
    try:
        registration = UserRegistration(
            email=body.email,
            hashed_password=UserService.hash_password(body.password),
            role=role,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    try:
        user = await svc.register(registration, body.home_university_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return user_response(user)


@router.get("", response_model=list[UserResponse])
async def list_users(_admin: AdminDep, svc: UserServiceDep) -> list[UserResponse]:
    """Return all users — ADMIN only."""
    return [user_response(u) for u in await svc.list_all()]


@router.get("/me", response_model=UserResponse)
def get_me(user: CurrentUserDep) -> UserResponse:
    """Return the current user's profile."""
    return user_response(user)


@router.get("/me/settings", response_model=UserSettings)
async def read_settings(user: CurrentUserDep, svc: UserServiceDep) -> UserSettings:
    """The caller's own settings: the university whose guidelines come first."""
    return UserSettings(home_university_id=await svc.home_university(user.id))


@router.patch("/me/settings", response_model=UserSettings)
async def update_settings(
    body: UserSettings, user: CurrentUserDep, svc: UserServiceDep
) -> UserSettings:
    """Set the caller's home university, or clear it with null.

    Not checked against the catalog, which identity does not know: an id
    that names no university only means no set is shown first.
    """
    await svc.set_home_university(user.id, body.home_university_id)
    return UserSettings(home_university_id=body.home_university_id)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID, _admin: AdminDep, svc: UserServiceDep
) -> None:
    """Delete a user — ADMIN only."""
    await svc.delete(user_id)


@router.patch("/me/password", response_model=LoginResponse)
async def change_password(
    body: ChangePasswordRequest,
    response: Response,
    user: CurrentUserDep,
    svc: UserServiceDep,
    token_store: TokenStoreDep,
    _rl: Annotated[None, Depends(login_rate_limit)],
) -> LoginResponse:
    """Change the current user's password, confirmed with the current one.

    Every session the user has ends with it, this one included; the caller
    gets a new one back, so only the browser that made the change stays in.
    """
    try:
        await svc.change_password(user.id, body.current_password, body.new_password)
    except WrongPasswordError as exc:
        # 403, not 401: the session is fine, and a 401 sends the client off to
        # renew it and repeat the request.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Aktualne hasło jest nieprawidłowe.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    await token_store.end_sessions(user.id, REFRESH_TTL)
    return LoginResponse(access_token=start_session(response, user))
