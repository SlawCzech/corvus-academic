"""Thesis-draft upload and listing endpoints."""

import uuid

import structlog
from fastapi import APIRouter, HTTPException, Response, UploadFile, status

from src.mentoring.application.exceptions import (
    DraftNotFoundError,
    StudentNotFoundError,
)
from src.mentoring.infrastructure.dependencies import CallerDep, DraftServiceDep
from src.mentoring.infrastructure.errors import not_found
from src.mentoring.infrastructure.schemas import DraftResponse, draft_response
from src.shared.downloads import attachment_response, read_upload

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter(prefix="/students", tags=["mentoring"])


@router.post(
    "/{student_id}/drafts",
    response_model=DraftResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_draft(
    student_id: uuid.UUID,
    file: UploadFile,
    caller: CallerDep,
    svc: DraftServiceDep,
) -> DraftResponse:
    """Upload the next version of a student's thesis.

    The PDF/DOCX is parsed in-process — the payoff of folding the old parser
    service into `app` — and stored, file and text, as version N+1.
    """
    data = await read_upload(file)
    try:
        draft = await svc.upload(
            caller,
            student_id,
            filename=file.filename or "",
            data=data,
            content_type=file.content_type or "",
        )
    except StudentNotFoundError as exc:
        raise not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except Exception as exc:
        logger.error(
            "draft_extraction_failed", student_id=str(student_id), error=str(exc)
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Could not read the document: {exc}",
        ) from exc
    return draft_response(draft)


@router.get("/{student_id}/drafts", response_model=list[DraftResponse])
async def list_drafts(
    student_id: uuid.UUID,
    caller: CallerDep,
    svc: DraftServiceDep,
) -> list[DraftResponse]:
    """Return a student's uploaded versions, newest first."""
    try:
        drafts = await svc.list_drafts(caller, student_id)
    except StudentNotFoundError as exc:
        raise not_found(exc) from exc
    return [draft_response(d) for d in drafts]


@router.post(
    "/{student_id}/drafts/{draft_id}/accept", response_model=list[DraftResponse]
)
async def accept_draft(
    student_id: uuid.UUID,
    draft_id: uuid.UUID,
    caller: CallerDep,
    svc: DraftServiceDep,
) -> list[DraftResponse]:
    """Mark a version as final. The others are purged after a grace period."""
    try:
        views = await svc.accept(caller, student_id, draft_id)
    except (StudentNotFoundError, DraftNotFoundError) as exc:
        raise not_found(exc) from exc
    return [draft_response(v) for v in views]


@router.delete(
    "/{student_id}/drafts/{draft_id}/accept", response_model=list[DraftResponse]
)
async def clear_draft_acceptance(
    student_id: uuid.UUID,
    draft_id: uuid.UUID,
    caller: CallerDep,
    svc: DraftServiceDep,
) -> list[DraftResponse]:
    """Undo an acceptance; before the grace period ends, nothing is purged."""
    try:
        views = await svc.clear_acceptance(caller, student_id, draft_id)
    except StudentNotFoundError as exc:
        raise not_found(exc) from exc
    return [draft_response(v) for v in views]


@router.delete("/{student_id}/drafts/{draft_id}", response_model=list[DraftResponse])
async def purge_draft(
    student_id: uuid.UUID,
    draft_id: uuid.UUID,
    caller: CallerDep,
    svc: DraftServiceDep,
) -> list[DraftResponse]:
    """Delete a version's text and file now. Its row stays in the history."""
    try:
        views = await svc.purge(caller, student_id, draft_id)
    except (StudentNotFoundError, DraftNotFoundError) as exc:
        raise not_found(exc) from exc
    return [draft_response(v) for v in views]


@router.get("/{student_id}/drafts/{draft_id}/file")
async def download_draft(
    student_id: uuid.UUID,
    draft_id: uuid.UUID,
    caller: CallerDep,
    svc: DraftServiceDep,
) -> Response:
    """Return the original upload of one version, as an attachment."""
    try:
        stored, data = await svc.download(caller, student_id, draft_id)
    except (StudentNotFoundError, DraftNotFoundError) as exc:
        raise not_found(exc) from exc
    return attachment_response(stored, data)
