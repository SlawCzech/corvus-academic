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
from src.identity.infrastructure.repositories import ApiKeyRepository
from src.mentoring.application.action_service import ActionService
from src.mentoring.application.agent_client import BYOK, AgentClient, KeyLoader
from src.mentoring.application.dashboard_service import DashboardService
from src.mentoring.application.demo_roster import DemoRoster
from src.mentoring.application.draft_service import DraftService
from src.mentoring.application.fragment_service import FragmentService
from src.mentoring.application.model_service import ModelService
from src.mentoring.application.student_deletion import StudentDeletionService
from src.mentoring.application.student_service import Caller, StudentService
from src.mentoring.infrastructure.guidelines_adapter import CatalogGuidelineSource
from src.mentoring.infrastructure.orm import DraftFileModel
from src.mentoring.infrastructure.repositories import (
    AgentActionRepository,
    MeetingNoteRepository,
    ModelSettingRepository,
    StudentRepository,
    ThesisDraftRepository,
    ThesisFragmentRepository,
    ThesisPartRepository,
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


def get_key_loader(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> KeyLoader:
    """A loader for the caller's own provider keys, for this request only.

    Nothing is decrypted here: the service calls the loader once it knows
    which provider the run needs, and only for that one. Injected on the
    endpoints that dispatch work and nowhere else — listing students has no
    business decrypting anybody's key.
    """
    repo = ApiKeyRepository(session)

    async def load(provider: str) -> BYOK | None:
        api_key = await load_api_key(repo, user.id, provider)
        if api_key is None:
            return None
        return BYOK(provider=api_key.provider, api_key=api_key.key)

    return load


def get_agent_client(request: Request) -> AgentClient:
    """Wrap the process-wide HTTP client kept in application state."""
    client: httpx.AsyncClient = request.app.state.http_client
    return AgentClient(client, settings.agent_url)


def get_model_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    agent: Annotated[AgentClient, Depends(get_agent_client)],
) -> ModelService:
    return ModelService(
        ModelSettingRepository(session), agent, settings.local_models_enabled
    )


def require_model_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Only an admin decides which local models promoters may use."""
    if not user.can(Permission.MANAGE_MODELS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Model management permission required",
        )
    return user


def get_action_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    students: Annotated[StudentService, Depends(get_student_service)],
    agent: Annotated[AgentClient, Depends(get_agent_client)],
    catalog: Annotated[GuidelineCatalog, Depends(get_catalog)],
    models: Annotated[ModelService, Depends(get_model_service)],
) -> ActionService:
    return ActionService(
        students,
        AgentActionRepository(session),
        ThesisDraftRepository(session),
        agent,
        CatalogGuidelineSource(catalog),
        models,
        ThesisPartRepository(session),
        ThesisFragmentRepository(session),
    )


def get_draft_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    students: Annotated[StudentService, Depends(get_student_service)],
) -> DraftService:
    return DraftService(
        students, ThesisDraftRepository(session), SqlFileStore(session, DraftFileModel)
    )


def get_fragment_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    students: Annotated[StudentService, Depends(get_student_service)],
) -> FragmentService:
    return FragmentService(
        students,
        ThesisPartRepository(session),
        ThesisFragmentRepository(session),
        SqlFileStore(session, DraftFileModel),
    )


def get_demo_roster(
    students: Annotated[StudentService, Depends(get_student_service)],
    drafts: Annotated[DraftService, Depends(get_draft_service)],
    catalog: Annotated[GuidelineCatalog, Depends(get_catalog)],
) -> DemoRoster:
    return DemoRoster(students, drafts, CatalogGuidelineSource(catalog))


def get_student_deletion_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    students: Annotated[StudentService, Depends(get_student_service)],
    agent: Annotated[AgentClient, Depends(get_agent_client)],
) -> StudentDeletionService:
    return StudentDeletionService(
        students,
        StudentRepository(session),
        ThesisDraftRepository(session),
        SqlFileStore(session, DraftFileModel),
        agent,
    )


def get_dashboard_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    students: Annotated[StudentService, Depends(get_student_service)],
    actions: Annotated[ActionService, Depends(get_action_service)],
) -> DashboardService:
    return DashboardService(students, AgentActionRepository(session), actions)


# ---------- Annotated aliases — what every endpoint actually types ----------

CallerDep = Annotated[Caller, Depends(get_caller)]
TokenDep = Annotated[str, Depends(get_bearer_token)]
KeyLoaderDep = Annotated[KeyLoader, Depends(get_key_loader)]
AgentClientDep = Annotated[AgentClient, Depends(get_agent_client)]
StudentServiceDep = Annotated[StudentService, Depends(get_student_service)]
ActionServiceDep = Annotated[ActionService, Depends(get_action_service)]
DraftServiceDep = Annotated[DraftService, Depends(get_draft_service)]
FragmentServiceDep = Annotated[FragmentService, Depends(get_fragment_service)]
DemoRosterDep = Annotated[DemoRoster, Depends(get_demo_roster)]
DashboardServiceDep = Annotated[DashboardService, Depends(get_dashboard_service)]
StudentDeletionServiceDep = Annotated[
    StudentDeletionService, Depends(get_student_deletion_service)
]
ModelServiceDep = Annotated[ModelService, Depends(get_model_service)]
ModelAdminDep = Annotated[User, Depends(require_model_admin)]
