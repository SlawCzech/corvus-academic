"""FastAPI dependency providers for the guideline catalog.

Like mentoring's, the one file here that imports from ``identity``: the
catalog needs to know who is asking, identity never imports anything back.
"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.guidelines.application.admin_service import GuidelineAdminService
from src.guidelines.application.catalog import GuidelineCatalog
from src.guidelines.infrastructure.orm import SourceFileModel
from src.guidelines.infrastructure.repositories import CatalogRepository
from src.identity.domain.user import Permission, User
from src.identity.infrastructure.dependencies import get_current_user
from src.shared.database import get_db_session
from src.shared.sql_file_store import SqlFileStore


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


ReaderDep = Annotated[Reader, Depends(get_reader)]
GuidelineAdminDep = Annotated[User, Depends(require_guideline_admin)]
CatalogDep = Annotated[GuidelineCatalog, Depends(get_catalog)]
AdminServiceDep = Annotated[GuidelineAdminService, Depends(get_admin_service)]
