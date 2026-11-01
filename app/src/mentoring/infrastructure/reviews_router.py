"""One-off review endpoints: making one, the history, promotion.

Only what a student does not already have. Once it exists, a review's actions,
thesis file and delete are the `/students/{id}` ones: see ADR 0017.
"""

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Form, HTTPException, UploadFile, status

from src.mentoring.application.exceptions import StudentNotFoundError
from src.mentoring.domain.student import ThesisType
from src.mentoring.infrastructure.dependencies import CallerDep, ReviewServiceDep
from src.mentoring.infrastructure.errors import conflict, not_found
from src.mentoring.infrastructure.schemas import (
    ReviewResponse,
    StudentResponse,
    TitlePageResponse,
    review_response,
    student_response,
    title_page_response,
)
from src.shared.downloads import read_upload

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter(prefix="/reviews", tags=["mentoring"])


@router.post("", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_review(
    file: UploadFile,
    full_name: Annotated[str, Form(min_length=1, max_length=255)],
    field_of_study: Annotated[str, Form(min_length=1, max_length=255)],
    thesis_type: Annotated[ThesisType, Form()],
    caller: CallerDep,
    svc: ReviewServiceDep,
    current_topic: Annotated[str | None, Form()] = None,
    research_area: Annotated[str | None, Form(max_length=255)] = None,
    research_aim: Annotated[str | None, Form(max_length=4000)] = None,
) -> ReviewResponse:
    """Store a thesis to review once, with no student on the roster.

    Starts no action: that is the ordinary `POST /students/{id}/actions`.
    """
    data = await read_upload(file)
    try:
        review = await svc.create(
            caller,
            full_name=full_name,
            field_of_study=field_of_study,
            thesis_type=thesis_type,
            filename=file.filename or "",
            data=data,
            content_type=file.content_type or "",
            topic=current_topic,
            research_area=research_area,
            research_aim=research_aim,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except Exception as exc:
        logger.error("review_extraction_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Could not read the document: {exc}",
        ) from exc
    return review_response(review)


@router.post("/title-page", response_model=TitlePageResponse)
async def read_title_page(
    file: UploadFile,
    caller: CallerDep,
    svc: ReviewServiceDep,
) -> TitlePageResponse:
    """Suggest the form's fields from a thesis's title page, with no model.

    Stores nothing: the thesis is kept only once the form is sent.
    """
    data = await read_upload(file)
    try:
        page = svc.suggest(file.filename or "", data, file.content_type or "")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except Exception as exc:
        logger.error("title_page_extraction_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Could not read the document: {exc}",
        ) from exc
    return title_page_response(page)


@router.get("", response_model=list[ReviewResponse])
async def list_reviews(
    caller: CallerDep,
    svc: ReviewServiceDep,
) -> list[ReviewResponse]:
    """Return the caller's one-off reviews, newest first."""
    return [review_response(r) for r in await svc.list_reviews(caller)]


@router.post("/{review_id}/promote", response_model=StudentResponse)
async def promote_review(
    review_id: uuid.UUID,
    caller: CallerDep,
    svc: ReviewServiceDep,
) -> StudentResponse:
    """Put the review's author on the roster. Results and thesis go along."""
    try:
        student = await svc.promote(caller, review_id)
    except StudentNotFoundError as exc:
        raise not_found(exc) from exc
    except ValueError as exc:
        raise conflict(exc) from exc
    return student_response(student)
