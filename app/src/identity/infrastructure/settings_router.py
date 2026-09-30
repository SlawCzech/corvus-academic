"""Per-user provider-key settings — BYOK."""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from src.identity.application.api_keys import get_api_key_status
from src.identity.application.key_check import KeyVerdict
from src.identity.domain.user import User
from src.identity.infrastructure.dependencies import (
    KeyCheckerDep,
    UserRepoDep,
    require_ai_user,
)
from src.identity.infrastructure.schemas import (
    ApiKeyRequest,
    ApiKeySavedResponse,
    ApiKeyStatusResponse,
)
from src.identity.infrastructure.secrets import get_secret_service

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

# A provider key only pays for AI actions, and only promoters run those.
AiUserDep = Annotated[User, Depends(require_ai_user)]


@router.patch("/api-key", response_model=ApiKeySavedResponse)
async def set_api_key(
    body: ApiKeyRequest,
    user: AiUserDep,
    repo: UserRepoDep,
    checker: KeyCheckerDep,
) -> ApiKeySavedResponse:
    """Store the caller's own provider key, encrypted — if the provider takes it.

    Every promoter, each with their own: the key is billed to their account
    and used only for the actions they trigger. A key the provider refuses is
    not stored, so the one already saved keeps working.
    """
    verdict = await checker.check(body.provider, body.api_key)
    if verdict is KeyVerdict.REJECTED:
        logger.info("api_key_rejected", user_id=str(user.id), provider=body.provider)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The provider rejected this key",
        )
    encrypted = get_secret_service().encrypt(body.api_key)
    await repo.update_api_key(user.id, encrypted, provider=body.provider)
    # The provider is worth an audit line; the key is never logged.
    logger.info(
        "api_key_stored",
        user_id=str(user.id),
        provider=body.provider,
        verdict=str(verdict),
    )
    return ApiKeySavedResponse(
        configured=True,
        provider=body.provider,
        verified=verdict is KeyVerdict.ACCEPTED,
    )


@router.delete("/api-key", response_model=ApiKeyStatusResponse)
async def delete_api_key(
    user: AiUserDep, repo: UserRepoDep
) -> ApiKeyStatusResponse:
    """Remove the caller's key — actions fall back to the self-hosted model."""
    await repo.update_api_key(user.id, None)
    logger.info("api_key_removed", user_id=str(user.id))
    return ApiKeyStatusResponse(configured=False)


@router.get("/api-key/status", response_model=ApiKeyStatusResponse)
async def read_api_key_status(
    user: AiUserDep, repo: UserRepoDep
) -> ApiKeyStatusResponse:
    """Return whether the caller has a key configured, and for which provider."""
    result = await get_api_key_status(repo, user.id)
    return ApiKeyStatusResponse(configured=result.configured, provider=result.provider)
