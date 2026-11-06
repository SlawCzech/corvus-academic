"""Per-user provider-key settings — BYOK, one key per provider."""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from src.identity.application.api_keys import SUPPORTED_PROVIDERS, get_api_key_status
from src.identity.application.key_check import KeyVerdict
from src.identity.domain.user import User
from src.identity.infrastructure.dependencies import (
    ApiKeyRepoDep,
    KeyCheckerDep,
    require_key_holder,
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
AiUserDep = Annotated[User, Depends(require_key_holder)]


async def _status(repo: ApiKeyRepoDep, user: User) -> ApiKeyStatusResponse:
    result = await get_api_key_status(repo, user.id)
    return ApiKeyStatusResponse(
        configured=result.configured, providers=list(result.providers)
    )


@router.patch("/api-key", response_model=ApiKeySavedResponse)
async def set_api_key(
    body: ApiKeyRequest,
    user: AiUserDep,
    repo: ApiKeyRepoDep,
    checker: KeyCheckerDep,
) -> ApiKeySavedResponse | JSONResponse:
    """Store the caller's key for one provider, encrypted — if the provider takes it.

    Every promoter, each with their own: a key is billed to their account
    and used only for the actions they run on it. It replaces an earlier key
    for the same provider and leaves the other provider's key alone. A key
    the provider refuses is not stored, so the one already saved keeps working;
    the refusal carries the provider's own message, when it gave one.
    """
    check = await checker.check(body.provider, body.api_key)
    verdict = check.verdict
    if verdict is KeyVerdict.REJECTED:
        # The provider's message is for the promoter, not the log: a provider
        # may quote part of the key back in it.
        logger.info("api_key_rejected", user_id=str(user.id), provider=body.provider)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "detail": "The provider rejected this key",
                "provider_message": check.provider_message,
            },
        )
    encrypted = get_secret_service().encrypt(body.api_key)
    await repo.upsert(user.id, body.provider, encrypted)
    # The provider is worth an audit line; the key is never logged.
    logger.info(
        "api_key_stored",
        user_id=str(user.id),
        provider=body.provider,
        verdict=str(verdict),
    )
    current = await _status(repo, user)
    return ApiKeySavedResponse(
        configured=current.configured,
        providers=current.providers,
        verified=verdict is KeyVerdict.ACCEPTED,
    )


@router.delete("/api-key/{provider}", response_model=ApiKeyStatusResponse)
async def delete_api_key(
    provider: str, user: AiUserDep, repo: ApiKeyRepoDep
) -> ApiKeyStatusResponse:
    """Remove the caller's key for one provider; idempotent.

    Actions that asked for that provider are refused from now on; the other
    provider's key is unaffected.
    """
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Unknown provider"
        )
    if await repo.delete(user.id, provider):
        logger.info("api_key_removed", user_id=str(user.id), provider=provider)
    return await _status(repo, user)


@router.get("/api-key/status", response_model=ApiKeyStatusResponse)
async def read_api_key_status(
    user: AiUserDep, repo: ApiKeyRepoDep
) -> ApiKeyStatusResponse:
    """Return which providers the caller has a key for."""
    return await _status(repo, user)
