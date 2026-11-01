"""User management endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.identity.application.user_service import UserService, WrongPasswordError
from src.identity.domain.user import Role, UserRegistration
from src.identity.infrastructure.dependencies import (
    AdminDep,
    CurrentUserDep,
    UserServiceDep,
)
from src.identity.infrastructure.limiter import login_rate_limit
from src.identity.infrastructure.schemas import (
    ChangePasswordRequest,
    RegisterRequest,
    UserResponse,
    user_response,
)

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
        user = await svc.register(registration)
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


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID, _admin: AdminDep, svc: UserServiceDep
) -> None:
    """Delete a user — ADMIN only."""
    await svc.delete(user_id)


@router.patch("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    user: CurrentUserDep,
    svc: UserServiceDep,
    _rl: Annotated[None, Depends(login_rate_limit)],
) -> None:
    """Change the current user's password, confirmed with the current one."""
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
