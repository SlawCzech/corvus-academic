"""Student roster and meeting-note endpoints."""

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, HTTPException, Query, status

from src.mentoring.application.exceptions import (
    AgentUnavailableError,
    OneOffReviewError,
    StudentNotFoundError,
)
from src.mentoring.domain.student import StudentStatus
from src.mentoring.infrastructure.demo_fixtures import load as load_demo
from src.mentoring.infrastructure.dependencies import (
    CallerDep,
    DemoRosterDep,
    StudentDeletionServiceDep,
    StudentServiceDep,
    TokenDep,
)
from src.mentoring.infrastructure.errors import conflict, not_found
from src.mentoring.infrastructure.schemas import (
    DemoSeedResponse,
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
            research_area=body.research_area,
            research_aim=body.research_aim,
            guideline_set_id=body.guideline_set_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    logger.info(
        "student_created", student_id=str(student.id), promotor_id=str(caller.user_id)
    )
    return student_response(student)


@router.post(
    "/demo", response_model=DemoSeedResponse, status_code=status.HTTP_201_CREATED
)
async def seed_demo_students(
    caller: CallerDep, roster: DemoRosterDep
) -> DemoSeedResponse:
    """Put the demo students on the caller's roster — those not there yet.

    For someone trying Corvus out: eight fictional students with notes and
    theses built to exercise the AI actions. They are ordinary students once
    created, removed with the ordinary delete.
    """
    report = await roster.seed(caller, load_demo())
    logger.info(
        "demo_students_seeded",
        promotor_id=str(caller.user_id),
        created=len(report.created),
        skipped=len(report.skipped),
    )
    return DemoSeedResponse(
        created=[s.full_name for s in report.created], skipped=report.skipped
    )


@router.get("", response_model=list[StudentResponse])
async def list_students(
    caller: CallerDep,
    svc: StudentServiceDep,
    # Named `status_filter` locally because `status` is fastapi's status module
    # here; the query parameter itself stays `?status=`.
    status_filter: Annotated[StudentStatus | None, Query(alias="status")] = None,
) -> list[StudentResponse]:
    """Return the caller's students — every promoter's, for an admin."""
    students = await svc.list_students(caller, status=status_filter, one_off=False)
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
    `propose_topic` action. `index_number`, `current_topic`, `research_area`,
    `research_aim` and `guideline_set_id` sent as null are cleared.
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
            research_area=body.research_area,
            set_research_area="research_area" in given,
            research_aim=body.research_aim,
            set_research_aim="research_aim" in given,
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


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student(
    student_id: uuid.UUID,
    caller: CallerDep,
    token: TokenDep,
    svc: StudentDeletionServiceDep,
) -> None:
    """Delete a student for good: notes, versions, files and AI results.

    Irreversible, unlike moving the student to `archived`, which only starts
    the retention clock.
    """
    try:
        await svc.delete(caller, student_id, token)
    except StudentNotFoundError as exc:
        raise not_found(exc) from exc
    except AgentUnavailableError as exc:
        # Nothing was deleted: the student's AI results live in the agent too,
        # and a deletion that left them there would not be one.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The analysis service is unavailable",
        ) from exc


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
    except OneOffReviewError as exc:
        raise conflict(exc) from exc
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
