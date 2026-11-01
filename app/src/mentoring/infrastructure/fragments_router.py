"""Endpoints for the parts of a thesis and the fragments handed in for them."""

import uuid
from datetime import date
from typing import Annotated

import structlog
from fastapi import APIRouter, Form, HTTPException, Response, UploadFile, status

from src.mentoring.application.exceptions import (
    ActionNotFoundError,
    AgentUnavailableError,
    FragmentNotFoundError,
    OneOffReviewError,
    PartConflictError,
    PartNotFoundError,
    StudentNotFoundError,
)
from src.mentoring.application.fragment_service import FragmentUpload
from src.mentoring.infrastructure.dependencies import (
    CallerDep,
    FragmentFeedbackServiceDep,
    FragmentServiceDep,
    TimelineServiceDep,
    TokenDep,
)
from src.mentoring.infrastructure.errors import conflict, not_found
from src.mentoring.infrastructure.schemas import (
    FragmentFeedbackRequest,
    FragmentResponse,
    PartCreateRequest,
    PartResponse,
    PartUpdateRequest,
    TimelineResponse,
    fragment_response,
    part_response,
    timeline_response,
)
from src.shared.downloads import attachment_response, read_upload

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter(prefix="/students", tags=["mentoring"])


@router.post(
    "/{student_id}/parts",
    response_model=PartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_part(
    student_id: uuid.UUID,
    body: PartCreateRequest,
    caller: CallerDep,
    svc: FragmentServiceDep,
) -> PartResponse:
    """Add a part of the thesis ahead of time."""
    try:
        part = await svc.add_part(caller, student_id, body.name, body.due_on)
    except StudentNotFoundError as exc:
        raise not_found(exc) from exc
    except (PartConflictError, OneOffReviewError) as exc:
        raise conflict(exc) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return part_response(part)


@router.patch("/{student_id}/parts/{part_id}", response_model=list[PartResponse])
async def update_part(
    student_id: uuid.UUID,
    part_id: uuid.UUID,
    body: PartUpdateRequest,
    caller: CallerDep,
    svc: FragmentServiceDep,
) -> list[PartResponse]:
    """Rename a part, move it, or change its deadline; a null `due_on` clears it."""
    try:
        parts = await svc.update_part(
            caller,
            student_id,
            part_id,
            name=body.name,
            position=body.position,
            due_on=body.due_on,
            change_due_on="due_on" in body.model_fields_set,
        )
    except (StudentNotFoundError, PartNotFoundError) as exc:
        raise not_found(exc) from exc
    except PartConflictError as exc:
        raise conflict(exc) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return [part_response(p) for p in parts]


@router.delete(
    "/{student_id}/parts/{part_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_part(
    student_id: uuid.UUID,
    part_id: uuid.UUID,
    caller: CallerDep,
    svc: FragmentServiceDep,
) -> None:
    """Remove a part nothing was handed in for."""
    try:
        await svc.delete_part(caller, student_id, part_id)
    except (StudentNotFoundError, PartNotFoundError) as exc:
        raise not_found(exc) from exc
    except PartConflictError as exc:
        raise conflict(exc) from exc


@router.post(
    "/{student_id}/fragments",
    response_model=FragmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_fragment(
    student_id: uuid.UUID,
    part_name: Annotated[str, Form(min_length=1, max_length=255)],
    caller: CallerDep,
    svc: FragmentServiceDep,
    file: UploadFile | None = None,
    text: Annotated[str | None, Form()] = None,
    question: Annotated[str | None, Form(max_length=4000)] = None,
    received_on: Annotated[date | None, Form()] = None,
) -> FragmentResponse:
    """Record a fragment, as a file or as text pasted from a mail."""
    upload = FragmentUpload(text=text)
    if file is not None:
        upload = FragmentUpload(
            filename=file.filename or "",
            data=await read_upload(file),
            content_type=file.content_type or "",
            text=text,
        )
    try:
        fragment = await svc.upload(
            caller,
            student_id,
            part_name,
            upload,
            question=question,
            received_on=received_on,
        )
    except StudentNotFoundError as exc:
        raise not_found(exc) from exc
    except OneOffReviewError as exc:
        raise conflict(exc) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except Exception as exc:
        logger.error(
            "fragment_extraction_failed", student_id=str(student_id), error=str(exc)
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Could not read the document: {exc}",
        ) from exc
    return fragment_response(fragment)


@router.get("/{student_id}/fragments/{fragment_id}/file")
async def download_fragment(
    student_id: uuid.UUID,
    fragment_id: uuid.UUID,
    caller: CallerDep,
    svc: FragmentServiceDep,
) -> Response:
    """Return the original upload of one fragment, as an attachment."""
    try:
        stored, data = await svc.download(caller, student_id, fragment_id)
    except (StudentNotFoundError, FragmentNotFoundError) as exc:
        raise not_found(exc) from exc
    return attachment_response(stored, data)


@router.put(
    "/{student_id}/fragments/{fragment_id}/feedback", response_model=FragmentResponse
)
async def record_feedback(
    student_id: uuid.UUID,
    fragment_id: uuid.UUID,
    body: FragmentFeedbackRequest,
    caller: CallerDep,
    svc: FragmentFeedbackServiceDep,
) -> FragmentResponse:
    """Save the promoter's verdict and feedback. Saving again corrects them."""
    try:
        fragment = await svc.record(
            caller,
            student_id,
            fragment_id,
            body.verdict,
            feedback=body.feedback,
            source_action_id=body.source_action_id,
            next_due_on=body.next_due_on,
        )
    except (
        StudentNotFoundError,
        FragmentNotFoundError,
        ActionNotFoundError,
    ) as exc:
        raise not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return fragment_response(fragment)


@router.delete(
    "/{student_id}/fragments/{fragment_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_fragment(
    student_id: uuid.UUID,
    fragment_id: uuid.UUID,
    caller: CallerDep,
    token: TokenDep,
    svc: FragmentFeedbackServiceDep,
) -> None:
    """Take back a mistaken upload, with its file and its AI runs."""
    try:
        await svc.delete(caller, student_id, fragment_id, token)
    except (StudentNotFoundError, FragmentNotFoundError) as exc:
        raise not_found(exc) from exc
    except AgentUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The analysis service is unavailable",
        ) from exc


@router.get("/{student_id}/timeline", response_model=TimelineResponse)
async def get_timeline(
    student_id: uuid.UUID,
    caller: CallerDep,
    token: TokenDep,
    svc: TimelineServiceDep,
) -> TimelineResponse:
    """Return the student's parts, and everything that happened, newest first."""
    try:
        timeline = await svc.timeline(caller, student_id, token)
    except StudentNotFoundError as exc:
        raise not_found(exc) from exc
    return timeline_response(timeline)
