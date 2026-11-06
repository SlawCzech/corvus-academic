"""FastAPI dependency providers for the guideline catalog.

Like mentoring's, the one file here that imports from ``identity``: the
catalog needs to know who is asking, identity never imports anything back.
"""

from dataclasses import dataclass
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.guidelines.application.admin_service import GuidelineAdminService
from src.guidelines.application.catalog import GuidelineCatalog
from src.guidelines.application.rubric_drafting import (
    KeyLoader,
    ProviderKey,
    RubricDraftingService,
)
from src.guidelines.infrastructure.agent_drafter import AgentRubricDrafter
from src.guidelines.infrastructure.orm import SourceFileModel
from src.guidelines.infrastructure.repositories import CatalogRepository
from src.identity.application.api_keys import load_api_key
from src.identity.domain.user import Permission, User
from src.identity.infrastructure.dependencies import get_current_user
from src.identity.infrastructure.repositories import ApiKeyRepository
from src.shared.database import get_db_session
from src.shared.settings import settings
from src.shared.sql_file_store import SqlFileStore

_bearer = HTTPBearer()


@dataclass(frozen=True)
class Reader:
    """Who is reading the catalog, and whether they may see drafts."""

    can_manage: bool


def get_reader(user: Annotated[User, Depends(get_current_user)]) -> Reader:
    """Anyone who supervises students, or manages the catalog, may read it."""
    can_manage = user.can(Permission.MANAGE_GUIDELINES)
    if not (can_manage or user.can(Permission.MANAGE_STUDENTS)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guideline access permission required",
        )
    return Reader(can_manage=can_manage)


def require_guideline_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not user.can(Permission.MANAGE_GUIDELINES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guideline management permission required",
        )
    return user


def get_catalog(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> GuidelineCatalog:
    return GuidelineCatalog(
        CatalogRepository(session), SqlFileStore(session, SourceFileModel)
    )


def get_admin_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> GuidelineAdminService:
    return GuidelineAdminService(
        CatalogRepository(session), SqlFileStore(session, SourceFileModel)
    )


def get_drafting_service(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RubricDraftingService:
    client: httpx.AsyncClient = request.app.state.http_client
    return RubricDraftingService(
        CatalogRepository(session),
        SqlFileStore(session, SourceFileModel),
        AgentRubricDrafter(client, settings.agent_url),
    )


def get_bearer_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> str:
    """The caller's token, forwarded to `agent` so its own auth still works."""
    return credentials.credentials


def get_key_loader(
    user: Annotated[User, Depends(require_guideline_admin)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> KeyLoader:
    """The admin's own provider keys, opened one at a time when asked for."""
    repo = ApiKeyRepository(session)

    async def load(provider: str) -> ProviderKey | None:
        api_key = await load_api_key(repo, user.id, provider)
        if api_key is None:
            return None
        return ProviderKey(provider=api_key.provider, api_key=api_key.key)

    return load


ReaderDep = Annotated[Reader, Depends(get_reader)]
GuidelineAdminDep = Annotated[User, Depends(require_guideline_admin)]
CatalogDep = Annotated[GuidelineCatalog, Depends(get_catalog)]
AdminServiceDep = Annotated[GuidelineAdminService, Depends(get_admin_service)]
DraftingServiceDep = Annotated[RubricDraftingService, Depends(get_drafting_service)]
BearerTokenDep = Annotated[str, Depends(get_bearer_token)]
KeyLoaderDep = Annotated[KeyLoader, Depends(get_key_loader)]
