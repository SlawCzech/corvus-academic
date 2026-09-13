"""Admin-only endpoints — the login audit log."""

import uuid

from fastapi import APIRouter

from src.identity.infrastructure.dependencies import AdminDep, LoginEventRepoDep
from src.identity.infrastructure.schemas import LoginEventResponse, login_event_response

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/login-events", response_model=list[LoginEventResponse])
async def get_login_events(
    _admin: AdminDep,
    event_repo: LoginEventRepoDep,
    user_id: uuid.UUID | None = None,
    success: bool | None = None,
) -> list[LoginEventResponse]:
    """Return login audit events with optional filtering — ADMIN only."""
    events = await event_repo.find_all(user_id=user_id, success=success)
    return [login_event_response(e) for e in events]
