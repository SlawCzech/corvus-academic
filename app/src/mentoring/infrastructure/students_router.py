"""Student roster and meeting-note endpoints."""

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, HTTPException, Query, status

from src.mentoring.application.exceptions import StudentNotFoundError
from src.mentoring.domain.student import StudentStatus
from src.mentoring.infrastructure.dependencies import CallerDep, StudentServiceDep
from src.mentoring.infrastructure.errors import not_found
from src.mentoring.infrastructure.schemas import (
    MeetingNoteCreateRequest,
    MeetingNoteResponse,
    StudentCreateRequest,
    StudentResponse,
    StudentUpdateRequest,
    note_response,
    student_response,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter(prefix="/students", tags=["mentoring"])


# ---------- students ----------


@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def create_student(
    body: StudentCreateRequest,
    caller: CallerDep,
    svc: StudentServiceDep,
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
    return student_response(student)


@router.get("", response_model=list[StudentResponse])
async def list_students(
    caller: CallerDep,
    svc: StudentServiceDep,
    # Named `status_filter` locally because `status` is fastapi's status module
    # here; the query parameter itself stays `?status=`.
    status_filter: Annotated[StudentStatus | None, Query(alias="status")] = None,
) -> list[StudentResponse]:
    """Return the caller's students — every promoter's, for an admin."""
    students = await svc.list_students(caller, status=status_filter)
    return [student_response(s) for s in students]


@router.get("/{student_id}", response_model=StudentResponse)
async def get_student(
    student_id: uuid.UUID,
    caller: CallerDep,
    svc: StudentServiceDep,
) -> StudentResponse:
    """Return one student the caller is allowed to see."""
    try:
        return student_response(await svc.get(caller, student_id))
    except StudentNotFoundError as exc:
        raise not_found(exc) from exc


@router.patch("/{student_id}", response_model=StudentResponse)
async def update_student(
    student_id: uuid.UUID,
    body: StudentUpdateRequest,
    caller: CallerDep,
    svc: StudentServiceDep,
) -> StudentResponse:
    """Edit the student's details, topic, lifecycle status and/or guideline set.

    Manual topic entry here; the same field is also written by accepting a
    `propose_topic` action. `index_number`, `current_topic` and
    `guideline_set_id` sent as null are cleared.
    """
    given = body.model_fields_set
    try:
        student = await svc.update(
            caller,
            student_id,
            full_name=body.full_name,
            field_of_study=body.field_of_study,
            thesis_type=body.thesis_type,
            index_number=body.index_number,
            set_index_number="index_number" in given,
            current_topic=body.current_topic,
            clear_topic="current_topic" in given and body.current_topic is None,
            status=body.status,
            guideline_set_id=body.guideline_set_id,
            set_guidelines="guideline_set_id" in given,
        )
    except StudentNotFoundError as exc:
        raise not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return student_response(student)


# ---------- meeting notes ----------


@router.post(
    "/{student_id}/meeting-notes",
    response_model=MeetingNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_meeting_note(
    student_id: uuid.UUID,
    body: MeetingNoteCreateRequest,
    caller: CallerDep,
    svc: StudentServiceDep,
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
        raise not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    logger.info(
        "meeting_note_created", student_id=str(student_id), note_id=str(note.id)
    )
    return note_response(note)


@router.get("/{student_id}/meeting-notes", response_model=list[MeetingNoteResponse])
async def list_meeting_notes(
    student_id: uuid.UUID,
    caller: CallerDep,
    svc: StudentServiceDep,
) -> list[MeetingNoteResponse]:
    """Return a student's meeting notes, most recent meeting first."""
    try:
        notes = await svc.list_meeting_notes(caller, student_id)
    except StudentNotFoundError as exc:
        raise not_found(exc) from exc
    return [note_response(n) for n in notes]
