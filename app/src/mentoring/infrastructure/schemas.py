"""Pydantic request/response models for the mentoring API.

Each response model sits next to the function that builds it from a domain
entity — they are two views of the same fact, and changing one without the
other is exactly the mistake this pairing exists to make obvious.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from src.mentoring.application.dashboard_service import DashboardSummary
from src.mentoring.application.draft_service import DraftView
from src.mentoring.domain.action import ActionType, AgentAction
from src.mentoring.domain.student import (
    MeetingNote,
    Student,
    StudentStatus,
    ThesisType,
)

# ---------- students ----------


class StudentCreateRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    field_of_study: str = Field(min_length=1, max_length=255)
    thesis_type: ThesisType
    index_number: str | None = Field(default=None, max_length=50)


class StudentUpdateRequest(BaseModel):
    current_topic: str | None = Field(default=None, min_length=1)
    status: StudentStatus | None = None
    # Sent as null to clear the choice; left out to keep it.
    guideline_set_id: uuid.UUID | None = None


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
    closed_at: datetime | None
    guideline_set_id: uuid.UUID | None


def student_response(student: Student) -> StudentResponse:
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
        closed_at=student.closed_at,
        guideline_set_id=student.guideline_set_id,
    )


# ---------- meeting notes ----------


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


def note_response(note: MeetingNote) -> MeetingNoteResponse:
    return MeetingNoteResponse(
        id=note.id,
        student_id=note.student_id,
        promotor_id=note.promotor_id,
        occurred_at=note.occurred_at,
        content=note.content,
        source_action_id=note.source_action_id,
        created_at=note.created_at,
    )


# ---------- AI actions ----------


class ActionTriggerRequest(BaseModel):
    action_type: ActionType
    detail: str | None = Field(default=None, max_length=4000)
    model: str | None = None
    language: str = "pl"
    # Only read by generate_review; ignored by every other action type. An
    # unrecognized value falls back to "auto" on the agent side.
    review_tone: str = "auto"


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


def action_response(action: AgentAction) -> ActionResponse:
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


# ---------- thesis drafts ----------


class DraftResponse(BaseModel):
    """A stored version. The extracted text is never sent back wholesale."""

    id: uuid.UUID
    student_id: uuid.UUID
    version_number: int
    filename: str
    pages: int
    format: str
    char_count: int
    preview: str
    uploaded_by: uuid.UUID
    created_at: datetime
    has_file: bool
    file_size: int | None
    file_sha256: str | None
    is_accepted: bool
    purged_at: datetime | None
    purge_due_at: datetime | None


def draft_response(view: DraftView) -> DraftResponse:
    draft = view.draft
    return DraftResponse(
        id=draft.id,
        student_id=draft.student_id,
        version_number=draft.version_number,
        filename=draft.filename,
        pages=draft.pages,
        format=draft.format,
        char_count=draft.char_count,
        preview=draft.preview,
        uploaded_by=draft.uploaded_by,
        created_at=draft.created_at,
        has_file=draft.has_file,
        file_size=draft.file_size,
        file_sha256=draft.file_sha256,
        is_accepted=view.is_accepted,
        purged_at=draft.purged_at,
        purge_due_at=view.purge_due_at,
    )


# ---------- dashboard ----------


class RecentActivityResponse(BaseModel):
    student_id: uuid.UUID
    student_name: str
    action_type: str
    status: str
    updated_at: datetime


class DashboardSummaryResponse(BaseModel):
    active_students: int
    without_topic: int
    actions_in_progress: int
    recent_activity: list[RecentActivityResponse]


def dashboard_summary_response(summary: DashboardSummary) -> DashboardSummaryResponse:
    return DashboardSummaryResponse(
        active_students=summary.active_students,
        without_topic=summary.without_topic,
        actions_in_progress=summary.actions_in_progress,
        recent_activity=[
            RecentActivityResponse(
                student_id=a.student_id,
                student_name=a.student_name,
                action_type=a.action_type,
                status=a.status,
                updated_at=a.updated_at,
            )
            for a in summary.recent_activity
        ],
    )
