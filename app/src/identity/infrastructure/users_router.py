"""User management endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from src.identity.application.user_service import UserService, WrongPasswordError
from src.identity.domain.terms import CURRENT_TERMS_VERSION
from src.identity.domain.user import Role, UserRegistration
from src.identity.infrastructure.dependencies import (
    AdminDep,
    CurrentUserDep,
    TermsRepoDep,
    TokenStoreDep,
    UserServiceDep,
)
from src.identity.infrastructure.limiter import login_rate_limit
from src.identity.infrastructure.schemas import (
    AcceptTermsRequest,
    ChangePasswordRequest,
    LoginResponse,
    RegisterRequest,
    TermsStatusResponse,
    UserResponse,
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


@router.get("/me/terms", response_model=TermsStatusResponse)
async def get_my_terms(
    user: CurrentUserDep, terms: TermsRepoDep
) -> TermsStatusResponse:
    """The terms in force, and whether the caller has accepted them."""
    return TermsStatusResponse(
        current_version=CURRENT_TERMS_VERSION,
        accepted_at=await terms.accepted_at(user.id, CURRENT_TERMS_VERSION),
    )


@router.post("/me/terms", response_model=TermsStatusResponse)
async def accept_my_terms(
    body: AcceptTermsRequest, user: CurrentUserDep, terms: TermsRepoDep
) -> TermsStatusResponse:
    """Accept the terms in force. Accepting again keeps the first date.

    The body names the version the promoter read: if the text changed while
    the page was open, that is a 409, not an acceptance of a text they did
    not see.
    """
    if body.version != CURRENT_TERMS_VERSION:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Regulamin zmienił się w międzyczasie. Odśwież stronę.",
        )
    accepted = await terms.record(user.id, CURRENT_TERMS_VERSION)
    return TermsStatusResponse(
        current_version=CURRENT_TERMS_VERSION, accepted_at=accepted
    )


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
