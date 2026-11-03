"""Model catalog — which model each provider's key runs on.

The agent knows; the frontend never talks to the agent, so `app` passes it on.
"""

from typing import cast

from fastapi import APIRouter, HTTPException, status

from src.mentoring.application.exceptions import AgentUnavailableError
from src.mentoring.infrastructure.dependencies import (
    AgentClientDep,
    CallerDep,
    TokenDep,
)
from src.mentoring.infrastructure.schemas import ModelCatalogResponse

router = APIRouter(prefix="/models", tags=["mentoring"])


@router.get("", response_model=ModelCatalogResponse)
async def list_models(
    # Unused, but resolving it is the check: only people who supervise
    # students get a model list.
    caller: CallerDep,
    token: TokenDep,
    agent: AgentClientDep,
) -> ModelCatalogResponse:
    """The model each provider runs on."""
    try:
        data = await agent.list_models(token)
    except AgentUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The analysis service is unavailable",
        ) from exc
    return ModelCatalogResponse(byok=cast(dict[str, str], data.get("byok") or {}))
