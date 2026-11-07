"""User management endpoints."""

import dataclasses
import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, status

from src.identity.application.user_service import (
    EmailTakenError,
    SamePasswordError,
    WrongPasswordError,
)
from src.identity.domain.terms import CURRENT_TERMS_VERSION
from src.identity.domain.user import Role
from src.identity.infrastructure.dependencies import (
    AccessRequestRepoDep,
    AdminDep,
    CurrentUserDep,
    SessionUserDep,
    TermsRepoDep,
    TokenStoreDep,
    UserServiceDep,
)
from src.identity.infrastructure.limiter import login_rate_limit
from src.identity.infrastructure.schemas import (
    AcceptTermsRequest,
    ChangePasswordRequest,
    CreatedUserResponse,
    LoginResponse,
    RegisterRequest,
    TemporaryPasswordResponse,
    TermsStatusResponse,
    UserResponse,
    UserSettings,
    user_response,
)
from src.identity.infrastructure.session import REFRESH_TTL, start_session

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "", response_model=CreatedUserResponse, status_code=status.HTTP_201_CREATED
)
async def create_user(
    body: RegisterRequest,
    admin: AdminDep,
    svc: UserServiceDep,
    requests: AccessRequestRepoDep,
) -> CreatedUserResponse:
    """Create an account with a temporary password — ADMIN only.

    The admin passes the password on with the invitation; the first login
    can only replace it. A pending access request from the same address is
    closed, since it has been answered.
    """
    try:
        user, temporary = await svc.register_with_temporary_password(
            body.email, Role(body.role), body.home_university_id
        )
    except EmailTakenError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Konto z tym adresem już istnieje.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    closed = await requests.delete_by_email(user.email)
    logger.info(
        "user_created_by_admin",
        user_id=str(user.id),
        admin=str(admin.id),
        access_requests_closed=closed,
    )
    return CreatedUserResponse(
        **user_response(user).model_dump(), temporary_password=temporary
    )


@router.get("", response_model=list[UserResponse])
async def list_users(_admin: AdminDep, svc: UserServiceDep) -> list[UserResponse]:
    """Return all users — ADMIN only."""
    return [user_response(u) for u in await svc.list_all()]


@router.get("/me", response_model=UserResponse)
def get_me(user: SessionUserDep) -> UserResponse:
    """Return the current user's profile, a temporary password or not."""
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


@router.post("/{user_id}/password-reset", response_model=TemporaryPasswordResponse)
async def reset_password(
    user_id: uuid.UUID,
    admin: AdminDep,
    svc: UserServiceDep,
    token_store: TokenStoreDep,
) -> TemporaryPasswordResponse:
    """Give a user a temporary password — ADMIN only.

    For a forgotten password: Corvus sends no mail, so the admin passes it
    on. Every session the user has ends, and the next login can do nothing
    but replace it. An admin changes their own password in the profile.
    """
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Własne hasło zmień w profilu.",
        )
    temporary = await svc.set_temporary_password(user_id)
    if temporary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Nie ma takiego konta."
        )
    await token_store.end_sessions(user_id, REFRESH_TTL)
    logger.info("password_reset_by_admin", user_id=str(user_id), admin=str(admin.id))
    return TemporaryPasswordResponse(temporary_password=temporary)


@router.patch("/me/password", response_model=LoginResponse)
async def change_password(
    body: ChangePasswordRequest,
    response: Response,
    user: SessionUserDep,
    svc: UserServiceDep,
    token_store: TokenStoreDep,
    _rl: Annotated[None, Depends(login_rate_limit)],
) -> LoginResponse:
    """Change the current user's password, confirmed with the current one.

    Every session the user has ends with it, this one included; the caller
    gets a new one back, so only the browser that made the change stays in.
    The one endpoint open on a temporary password, which it replaces.
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
    except SamePasswordError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Nowe hasło musi być inne niż obecne.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    await token_store.end_sessions(user.id, REFRESH_TTL)
    own = dataclasses.replace(user, must_change_password=False)
    return LoginResponse(access_token=start_session(response, own))
