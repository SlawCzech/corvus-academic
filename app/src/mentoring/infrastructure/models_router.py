"""Model catalog endpoints — what promoters may pick, and what admins offer.

The agent knows what is installed; the admin decides what is offered. Both
lists go through `app`, since the frontend never talks to the agent.
"""

from fastapi import APIRouter, HTTPException, status

from src.mentoring.application.exceptions import AgentUnavailableError
from src.mentoring.application.model_service import ModelNotInstalledError
from src.mentoring.domain.model_policy import ModelPolicyError
from src.mentoring.infrastructure.dependencies import (
    CallerDep,
    ModelAdminDep,
    ModelServiceDep,
    TokenDep,
)
from src.mentoring.infrastructure.schemas import (
    AdminModelCatalogResponse,
    ModelCatalogResponse,
    ModelDefaultRequest,
    ModelEnabledRequest,
    admin_model_catalog_response,
    model_catalog_response,
)

router = APIRouter(prefix="/models", tags=["mentoring"])


def _agent_down(exc: AgentUnavailableError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="The analysis service is unavailable",
    )


@router.get("", response_model=ModelCatalogResponse)
async def list_models(
    # Unused, but resolving it is the check: only people who supervise
    # students (or admins) get a model list.
    caller: CallerDep,
    token: TokenDep,
    svc: ModelServiceDep,
) -> ModelCatalogResponse:
    """Installed models the admin has made available, and the default."""
    try:
        return model_catalog_response(await svc.promoter_catalog(token))
    except AgentUnavailableError as exc:
        raise _agent_down(exc) from exc


@router.get("/admin", response_model=AdminModelCatalogResponse)
async def admin_list_models(
    admin: ModelAdminDep,
    token: TokenDep,
    svc: ModelServiceDep,
) -> AdminModelCatalogResponse:
    """Every installed model, with whether it is offered and which is default."""
    try:
        return admin_model_catalog_response(await svc.admin_catalog(token))
    except AgentUnavailableError as exc:
        raise _agent_down(exc) from exc


@router.patch("/admin", response_model=AdminModelCatalogResponse)
async def admin_set_enabled(
    body: ModelEnabledRequest,
    admin: ModelAdminDep,
    token: TokenDep,
    svc: ModelServiceDep,
) -> AdminModelCatalogResponse:
    """Offer an installed model to promoters, or withdraw it."""
    try:
        catalog = await svc.set_enabled(token, body.name, body.enabled, admin.id)
    except AgentUnavailableError as exc:
        raise _agent_down(exc) from exc
    except ModelNotInstalledError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {body.name!r} is not installed on the server",
        ) from exc
    except ModelPolicyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return admin_model_catalog_response(catalog)


@router.put("/admin/default", response_model=AdminModelCatalogResponse)
async def admin_set_default(
    body: ModelDefaultRequest,
    admin: ModelAdminDep,
    token: TokenDep,
    svc: ModelServiceDep,
) -> AdminModelCatalogResponse:
    """Make an installed model the default — enabling it if it was not."""
    try:
        catalog = await svc.set_default(token, body.name, admin.id)
    except AgentUnavailableError as exc:
        raise _agent_down(exc) from exc
    except ModelNotInstalledError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {body.name!r} is not installed on the server",
        ) from exc
    return admin_model_catalog_response(catalog)
