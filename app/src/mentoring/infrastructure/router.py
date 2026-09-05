"""FastAPI router — student roster and meeting notes."""

import uuid
from datetime import datetime
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.identity.domain.user import Permission, User
from src.identity.infrastructure.router import get_current_user
from src.mentoring.application.action_service import (
    ActionNotFoundError,
    ActionService,
    UnsupportedActionError,
)
from src.mentoring.application.agent_client import (
    AgentClient,
    AgentUnavailableError,
)
from src.mentoring.application.student_service import (
    Caller,
    StudentNotFoundError,
    StudentService,
)
from src.mentoring.domain.action import ActionType, AgentAction
from src.mentoring.domain.student import (
    MeetingNote,
    Student,
    StudentStatus,
    ThesisType,
)
from src.mentoring.infrastructure.repositories import (
    AgentActionRepository,
    MeetingNoteRepository,
    StudentRepository,
)
from src.shared.database import get_db_session
from src.shared.settings import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter(prefix="/students", tags=["mentoring"])
_bearer = HTTPBearer()


# ---------- dependencies ----------


def require_students_access(user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency — assert MANAGE_STUDENTS permission."""
    if not user.can(Permission.MANAGE_STUDENTS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student management permission required",
        )
    return user


def get_caller(user: User = Depends(require_students_access)) -> Caller:
    """Project the authenticated user into the mentoring context."""
    return Caller(
        user_id=user.id,
        can_view_all=user.can(Permission.VIEW_ALL_STUDENTS),
    )


def get_student_service(
    session: AsyncSession = Depends(get_db_session),
) -> StudentService:
    return StudentService(StudentRepository(session), MeetingNoteRepository(session))


def get_bearer_token(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str:
    """The caller's raw token, forwarded to `agent` so its own auth still works."""
    return credentials.credentials


def get_agent_client(request: Request) -> AgentClient:
    """Wrap the process-wide HTTP client kept in application state."""
    client: httpx.AsyncClient = request.app.state.http_client
    return AgentClient(client, settings.agent_url)


def get_action_service(
    session: AsyncSession = Depends(get_db_session),
    students: StudentService = Depends(get_student_service),
    agent: AgentClient = Depends(get_agent_client),
) -> ActionService:
    return ActionService(students, AgentActionRepository(session), agent)


# ---------- schemas ----------


class StudentCreateRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    field_of_study: str = Field(min_length=1, max_length=255)
    thesis_type: ThesisType
    index_number: str | None = Field(default=None, max_length=50)


class StudentUpdateRequest(BaseModel):
    current_topic: str | None = Field(default=None, min_length=1)
    status: StudentStatus | None = None


class StudentResponse(BaseModel):
    id: uuid.UUID
    promotor_id: uuid.UUID
    full_name: str
    index_number: str | None
    field_of_study: str
    thesis_type: str
    current_topic: str | None
    current_topic_set_at: datetime | None
    status: str
    created_at: datetime
    updated_at: datetime


class MeetingNoteCreateRequest(BaseModel):
    content: str = Field(min_length=1)
    occurred_at: datetime | None = None


class MeetingNoteResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    promotor_id: uuid.UUID
    occurred_at: datetime
    content: str
    source_action_id: uuid.UUID | None
    created_at: datetime


class ActionTriggerRequest(BaseModel):
    action_type: ActionType
    detail: str | None = Field(default=None, max_length=4000)
    model: str | None = None
    language: str = "pl"


class ActionAcceptRequest(BaseModel):
    # Which of the proposed topics the promoter picked. Ignored by action
    # types that have nothing to choose between.
    topic_index: int = Field(default=0, ge=0)


class ActionResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    promotor_id: uuid.UUID
    action_type: str
    status: str
    task_id: str | None
    detail: str | None
    output: dict[str, Any] | None
    error: str | None
    accepted: bool
    accepted_at: datetime | None
    created_at: datetime
    updated_at: datetime


def _action_response(action: AgentAction) -> ActionResponse:
    return ActionResponse(
        id=action.id,
        student_id=action.student_id,
        promotor_id=action.promotor_id,
        action_type=str(action.action_type),
        status=str(action.status),
        task_id=action.task_id,
        detail=action.detail,
        output=action.output,
        error=action.error,
        accepted=action.accepted,
        accepted_at=action.accepted_at,
        created_at=action.created_at,
        updated_at=action.updated_at,
    )


def _student_response(student: Student) -> StudentResponse:
    return StudentResponse(
        id=student.id,
        promotor_id=student.promotor_id,
        full_name=student.full_name,
        index_number=student.index_number,
        field_of_study=student.field_of_study,
        thesis_type=str(student.thesis_type),
        current_topic=student.current_topic,
        current_topic_set_at=student.current_topic_set_at,
        status=str(student.status),
        created_at=student.created_at,
        updated_at=student.updated_at,
    )


def _note_response(note: MeetingNote) -> MeetingNoteResponse:
    return MeetingNoteResponse(
        id=note.id,
        student_id=note.student_id,
        promotor_id=note.promotor_id,
        occurred_at=note.occurred_at,
        content=note.content,
        source_action_id=note.source_action_id,
        created_at=note.created_at,
    )


def _not_found(exc: Exception) -> HTTPException:
    """Map an invisible-or-missing student (or one of its actions) to 404.

    Deliberately not 403: a promoter must not be able to probe whether some
    other promoter's student id exists.
    """
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail=f"Not found: {exc}"
    )


# ---------- student endpoints ----------


@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def create_student(
    body: StudentCreateRequest,
    caller: Caller = Depends(get_caller),
    svc: StudentService = Depends(get_student_service),
) -> StudentResponse:
    """Add a student to the caller's roster."""
    try:
        student = await svc.create(
            caller,
            full_name=body.full_name,
            field_of_study=body.field_of_study,
            thesis_type=body.thesis_type,
            index_number=body.index_number,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    logger.info(
        "student_created", student_id=str(student.id), promotor_id=str(caller.user_id)
    )
    return _student_response(student)


@router.get("", response_model=list[StudentResponse])
async def list_students(
    # Named `status_filter` locally because `status` is fastapi's status module
    # here; the query parameter itself stays `?status=`.
    status_filter: StudentStatus | None = Query(default=None, alias="status"),
    caller: Caller = Depends(get_caller),
    svc: StudentService = Depends(get_student_service),
) -> list[StudentResponse]:
    """Return the caller's students — every promoter's, for an admin."""
    students = await svc.list_students(caller, status=status_filter)
    return [_student_response(s) for s in students]


@router.get("/{student_id}", response_model=StudentResponse)
async def get_student(
    student_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    svc: StudentService = Depends(get_student_service),
) -> StudentResponse:
    """Return one student the caller is allowed to see."""
    try:
        return _student_response(await svc.get(caller, student_id))
    except StudentNotFoundError as exc:
        raise _not_found(exc) from exc


@router.patch("/{student_id}", response_model=StudentResponse)
async def update_student(
    student_id: uuid.UUID,
    body: StudentUpdateRequest,
    caller: Caller = Depends(get_caller),
    svc: StudentService = Depends(get_student_service),
) -> StudentResponse:
    """Set the student's current topic and/or lifecycle status.

    Manual topic entry today; from Phase 2 the same field is written by
    accepting a `propose_topic` action.
    """
    try:
        student = await svc.update(
            caller,
            student_id,
            current_topic=body.current_topic,
            status=body.status,
        )
    except StudentNotFoundError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return _student_response(student)


# ---------- meeting note endpoints ----------


@router.post(
    "/{student_id}/meeting-notes",
    response_model=MeetingNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_meeting_note(
    student_id: uuid.UUID,
    body: MeetingNoteCreateRequest,
    caller: Caller = Depends(get_caller),
    svc: StudentService = Depends(get_student_service),
) -> MeetingNoteResponse:
    """Record a meeting note for a student."""
    try:
        note = await svc.add_meeting_note(
            caller,
            student_id,
            content=body.content,
            occurred_at=body.occurred_at,
        )
    except StudentNotFoundError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    logger.info(
        "meeting_note_created", student_id=str(student_id), note_id=str(note.id)
    )
    return _note_response(note)


@router.get("/{student_id}/meeting-notes", response_model=list[MeetingNoteResponse])
async def list_meeting_notes(
    student_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    svc: StudentService = Depends(get_student_service),
) -> list[MeetingNoteResponse]:
    """Return a student's meeting notes, most recent meeting first."""
    try:
        notes = await svc.list_meeting_notes(caller, student_id)
    except StudentNotFoundError as exc:
        raise _not_found(exc) from exc
    return [_note_response(n) for n in notes]


# ---------- AI action endpoints ----------


@router.post(
    "/{student_id}/actions",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_action(
    student_id: uuid.UUID,
    body: ActionTriggerRequest,
    caller: Caller = Depends(get_caller),
    token: str = Depends(get_bearer_token),
    svc: ActionService = Depends(get_action_service),
) -> ActionResponse:
    """Run one AI action for a student and return the queued action record.

    Returns immediately: the work happens in the agent's Celery worker, and
    the caller polls the action's own endpoint for the outcome.
    """
    try:
        action = await svc.trigger(
            caller,
            student_id,
            action_type=body.action_type,
            token=token,
            detail=body.detail,
            model=body.model,
            language=body.language,
        )
    except StudentNotFoundError as exc:
        raise _not_found(exc) from exc
    except UnsupportedActionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except AgentUnavailableError as exc:
        # The attempt is recorded as failed; the promoter can retry.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The analysis service is unavailable",
        ) from exc
    return _action_response(action)


@router.get("/{student_id}/actions", response_model=list[ActionResponse])
async def list_actions(
    student_id: uuid.UUID,
    action_type: ActionType | None = Query(default=None, alias="type"),
    caller: Caller = Depends(get_caller),
    svc: ActionService = Depends(get_action_service),
) -> list[ActionResponse]:
    """Return a student's AI action history, newest first."""
    try:
        actions = await svc.list_actions(caller, student_id, action_type)
    except StudentNotFoundError as exc:
        raise _not_found(exc) from exc
    return [_action_response(a) for a in actions]


@router.get("/{student_id}/actions/{action_id}", response_model=ActionResponse)
async def get_action(
    student_id: uuid.UUID,
    action_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    token: str = Depends(get_bearer_token),
    svc: ActionService = Depends(get_action_service),
) -> ActionResponse:
    """Poll one action — refreshed from the agent while it is still running."""
    try:
        action = await svc.get_action(caller, student_id, action_id, token)
    except (StudentNotFoundError, ActionNotFoundError) as exc:
        raise _not_found(exc) from exc
    return _action_response(action)


@router.patch(
    "/{student_id}/actions/{action_id}/accept", response_model=ActionResponse
)
async def accept_action(
    student_id: uuid.UUID,
    action_id: uuid.UUID,
    body: ActionAcceptRequest,
    caller: Caller = Depends(get_caller),
    svc: ActionService = Depends(get_action_service),
) -> ActionResponse:
    """Accept an action's result — for a topic proposal, this sets the topic."""
    try:
        action = await svc.accept(
            caller, student_id, action_id, topic_index=body.topic_index
        )
    except (StudentNotFoundError, ActionNotFoundError) as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        # Accepting twice, accepting something still running, or picking a
        # topic index the model never proposed.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return _action_response(action)
