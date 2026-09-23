"""FastAPI dependency providers for the mentoring routers.

Every ``Depends(...)`` this bounded context needs, in one place, each paired
with an ``Annotated`` alias — endpoints take e.g. ``caller: CallerDep``
instead of ``caller: Caller = Depends(get_caller)``. Same wiring everywhere,
and never two endpoints resolving the same dependency two different ways.

This is also the one file in ``mentoring`` that imports from ``identity``
(``User``, ``Permission``, ``get_current_user``) — mentoring needs to know
who is asking; identity never imports anything back. The same goes for
``guidelines``: the catalog is wired in here, behind mentoring's own
``GuidelineSource`` port (``guidelines_adapter.py``).
"""

from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.guidelines.application.catalog import GuidelineCatalog
from src.guidelines.infrastructure.dependencies import get_catalog
from src.identity.application.api_keys import load_api_key
from src.identity.domain.user import Permission, User
from src.identity.infrastructure.dependencies import get_current_user
from src.identity.infrastructure.repositories import UserRepository
from src.mentoring.application.action_service import ActionService
from src.mentoring.application.agent_client import BYOK, AgentClient
from src.mentoring.application.dashboard_service import DashboardService
from src.mentoring.application.draft_service import DraftService
from src.mentoring.application.student_service import Caller, StudentService
from src.mentoring.infrastructure.guidelines_adapter import CatalogGuidelineSource
from src.mentoring.infrastructure.orm import DraftFileModel
from src.mentoring.infrastructure.repositories import (
    AgentActionRepository,
    MeetingNoteRepository,
    StudentRepository,
    ThesisDraftRepository,
)
from src.shared.database import get_db_session
from src.shared.settings import settings
from src.shared.sql_file_store import SqlFileStore

_bearer = HTTPBearer()


# ---------- providers ----------


def require_students_access(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """FastAPI dependency — assert MANAGE_STUDENTS permission."""
    if not user.can(Permission.MANAGE_STUDENTS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student management permission required",
        )
    return user


def get_caller(
    user: Annotated[User, Depends(require_students_access)],
) -> Caller:
    """Project the authenticated user into the mentoring context."""
    return Caller(
        user_id=user.id,
        can_view_all=user.can(Permission.VIEW_ALL_STUDENTS),
    )


def get_student_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    catalog: Annotated[GuidelineCatalog, Depends(get_catalog)],
) -> StudentService:
    return StudentService(
        StudentRepository(session),
        MeetingNoteRepository(session),
        CatalogGuidelineSource(catalog),
    )


def get_bearer_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> str:
    """The caller's raw token, forwarded to `agent` so its own auth still works."""
    return credentials.credentials


async def get_byok(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BYOK | None:
    """Decrypt the caller's own provider key, for this request only.

    Resolved on the endpoint that dispatches work and nowhere else: listing
    students has no business decrypting anybody's key.
    """
    api_key = await load_api_key(UserRepository(session), user.id)
    if api_key is None:
        return None
    return BYOK(provider=api_key.provider, api_key=api_key.key)


def get_agent_client(request: Request) -> AgentClient:
    """Wrap the process-wide HTTP client kept in application state."""
    client: httpx.AsyncClient = request.app.state.http_client
    return AgentClient(client, settings.agent_url)


def get_action_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    students: Annotated[StudentService, Depends(get_student_service)],
    agent: Annotated[AgentClient, Depends(get_agent_client)],
    catalog: Annotated[GuidelineCatalog, Depends(get_catalog)],
) -> ActionService:
    return ActionService(
        students,
        AgentActionRepository(session),
        ThesisDraftRepository(session),
        agent,
        CatalogGuidelineSource(catalog),
    )


def get_draft_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    students: Annotated[StudentService, Depends(get_student_service)],
) -> DraftService:
    return DraftService(
        students, ThesisDraftRepository(session), SqlFileStore(session, DraftFileModel)
    )


def get_dashboard_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    students: Annotated[StudentService, Depends(get_student_service)],
) -> DashboardService:
    return DashboardService(students, AgentActionRepository(session))


# ---------- Annotated aliases — what every endpoint actually types ----------

CallerDep = Annotated[Caller, Depends(get_caller)]
TokenDep = Annotated[str, Depends(get_bearer_token)]
BYOKDep = Annotated[BYOK | None, Depends(get_byok)]
StudentServiceDep = Annotated[StudentService, Depends(get_student_service)]
ActionServiceDep = Annotated[ActionService, Depends(get_action_service)]
DraftServiceDep = Annotated[DraftService, Depends(get_draft_service)]
DashboardServiceDep = Annotated[DashboardService, Depends(get_dashboard_service)]
