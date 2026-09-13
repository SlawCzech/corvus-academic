"""Access-request endpoints.

There is no self-signup: accounts are created by an admin (``POST /users``).
This is the on-ramp to that — a visitor leaves their email, an admin sees it
and decides whether to create an account. Nothing here issues credentials.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.identity.infrastructure.dependencies import AccessRequestRepoDep, AdminDep
from src.identity.infrastructure.limiter import access_request_rate_limit
from src.identity.infrastructure.models import AccessRequestModel
from src.identity.infrastructure.schemas import (
    AccessRequestCreate,
    AccessRequestResponse,
    access_request_response,
)

router = APIRouter(tags=["access-requests"])


@router.post(
    "/access-requests",
    response_model=AccessRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_access_request(
    body: AccessRequestCreate,
    repo: AccessRequestRepoDep,
    _rl: Annotated[None, Depends(access_request_rate_limit)],
) -> AccessRequestResponse:
    """Record a request for access — public, unauthenticated, rate-limited."""
    model = AccessRequestModel(
        id=uuid.uuid4(), email=body.email, created_at=datetime.now(UTC)
    )
    await repo.save(model)
    return access_request_response(model)


@router.get("/access-requests", response_model=list[AccessRequestResponse])
async def list_access_requests(
    _admin: AdminDep, repo: AccessRequestRepoDep
) -> list[AccessRequestResponse]:
    """Return pending access requests, newest first — ADMIN only."""
    return [access_request_response(r) for r in await repo.find_all()]


@router.delete("/access-requests/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_access_request(
    request_id: uuid.UUID, _admin: AdminDep, repo: AccessRequestRepoDep
) -> None:
    """Dismiss a request once handled (or as spam) — ADMIN only."""
    found = await repo.delete(request_id)
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
