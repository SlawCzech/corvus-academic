"""FastAPI router — student roster and meeting notes."""

import uuid
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.identity.domain.user import Permission, User
from src.identity.infrastructure.router import get_current_user
from src.mentoring.application.student_service import (
    Caller,
    StudentNotFoundError,
    StudentService,
)
from src.mentoring.domain.student import (
    MeetingNote,
    Student,
    StudentStatus,
    ThesisType,
)
from src.mentoring.infrastructure.repositories import (
    MeetingNoteRepository,
    StudentRepository,
)
from src.shared.database import get_db_session

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter(prefix="/students", tags=["mentoring"])


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


def _not_found(exc: StudentNotFoundError) -> HTTPException:
    """Map an invisible-or-missing student to 404.

    Deliberately not 403: a promoter must not be able to probe whether some
    other promoter's student id exists.
    """
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail=f"Student not found: {exc}"
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
