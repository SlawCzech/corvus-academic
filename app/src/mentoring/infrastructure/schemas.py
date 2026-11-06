"""Pydantic request/response models for the mentoring API.

Each response model sits next to the function that builds it from a domain
entity — they are two views of the same fact, and changing one without the
other is exactly the mistake this pairing exists to make obvious.
"""

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.document.title_page import TitlePage
from src.mentoring.application.action_service import ActionInProgress
from src.mentoring.application.dashboard_service import (
    DashboardSummary,
    FragmentAwaiting,
    PartOverdue,
)
from src.mentoring.application.draft_service import DraftView
from src.mentoring.application.review_service import ReviewView
from src.mentoring.application.timeline_service import (
    FragmentEntry,
    PartEntry,
    TimelineEvent,
    WorkTimeline,
)
from src.mentoring.domain.action import ActionType, AgentAction
from src.mentoring.domain.fragment import FragmentVerdict, ThesisFragment, ThesisPart
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
    research_area: str | None = Field(default=None, max_length=255)
    research_aim: str | None = Field(default=None, max_length=4000)


class StudentUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    field_of_study: str | None = Field(default=None, min_length=1, max_length=255)
    thesis_type: ThesisType | None = None
    # These four: sent as null to clear, left out to keep.
    research_area: str | None = Field(default=None, min_length=1, max_length=255)
    research_aim: str | None = Field(default=None, min_length=1, max_length=4000)
    current_topic: str | None = Field(default=None, min_length=1)
    guideline_set_id: uuid.UUID | None = None
    status: StudentStatus | None = None


class StudentResponse(BaseModel):
    id: uuid.UUID
    promotor_id: uuid.UUID
    full_name: str
    field_of_study: str
    thesis_type: str
    current_topic: str | None
    current_topic_set_at: datetime | None
    research_area: str | None
    research_aim: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    guideline_set_id: uuid.UUID | None
    is_one_off: bool


def student_response(student: Student) -> StudentResponse:
    return StudentResponse(
        id=student.id,
        promotor_id=student.promotor_id,
        full_name=student.full_name,
        field_of_study=student.field_of_study,
        thesis_type=str(student.thesis_type),
        current_topic=student.current_topic,
        current_topic_set_at=student.current_topic_set_at,
        research_area=student.research_area,
        research_aim=student.research_aim,
        status=str(student.status),
        created_at=student.created_at,
        updated_at=student.updated_at,
        closed_at=student.closed_at,
        guideline_set_id=student.guideline_set_id,
        is_one_off=student.is_one_off,
    )


class ReviewResponse(BaseModel):
    """A one-off review as the history lists it."""

    id: uuid.UUID
    full_name: str
    field_of_study: str
    thesis_type: str
    current_topic: str | None
    created_at: datetime
    filename: str
    purged_at: datetime | None
    purge_due_at: datetime | None


class TitlePageResponse(BaseModel):
    """What a title page suggests for the form; null for what was not found."""

    full_name: str | None
    field_of_study: str | None
    thesis_type: str | None
    current_topic: str | None


def title_page_response(page: TitlePage) -> TitlePageResponse:
    return TitlePageResponse(
        full_name=page.author,
        field_of_study=page.field_of_study,
        thesis_type=page.thesis_type,
        current_topic=page.title,
    )


def review_response(view: ReviewView) -> ReviewResponse:
    return ReviewResponse(
        id=view.student.id,
        full_name=view.student.full_name,
        field_of_study=view.student.field_of_study,
        thesis_type=str(view.student.thesis_type),
        current_topic=view.student.current_topic,
        created_at=view.student.created_at,
        filename=view.draft.draft.filename,
        purged_at=view.draft.draft.purged_at,
        purge_due_at=view.draft.purge_due_at,
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
    # Whose account the run goes on: a provider the caller has a key for.
    # Never guessed from the stored keys — nobody is billed without asking
    # for it. Missing is a 409 (ADR 0022).
    provider: Literal["claude", "openai"] | None = None
    language: str = "pl"
    # Only read by generate_review; ignored by every other action type. An
    # unrecognized value falls back to "auto" on the agent side.
    review_tone: str = "auto"
    # generate_review only: pause after the analyses so the promoter can
    # untick the findings the review must not use.
    review_findings_first: bool = False
    # review_fragment only: the fragment it reads.
    fragment_id: uuid.UUID | None = None


class ActionResumeRequest(BaseModel):
    # Indices into the findings of the paused review — the ones it may use.
    accepted_findings: list[int] = Field(default_factory=list[int])


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
    # Set when the promoter can fix the failure: `provider_no_credits`,
    # `provider_key_rejected`, `provider_rate_limited`.
    error_code: str | None = None
    # The provider whose account ran it; None for a run on a local model,
    # before ADR 0022.
    provider: str | None = None
    # Tokens spent — {input_tokens, output_tokens, total_tokens, by_model};
    # None before the agent reports any, and for actions older than the count.
    usage: dict[str, Any] | None = None
    accepted: bool
    accepted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    # Unfinished actions only: the agent's steps and those already done.
    progress: dict[str, Any] | None = None


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
        error_code=action.error_code,
        provider=action.provider,
        usage=action.usage,
        accepted=action.accepted,
        accepted_at=action.accepted_at,
        created_at=action.created_at,
        updated_at=action.updated_at,
        progress=action.progress,
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


class ActionInProgressResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    action_type: str
    status: str
    created_at: datetime
    updated_at: datetime


# ---------- parts and fragments ----------


class PartCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    due_on: date | None = None


class PartUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    position: int | None = None
    # A null here clears the deadline; leaving the field out keeps it.
    due_on: date | None = None


class PartResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    name: str
    position: int
    due_on: date | None


def part_response(part: ThesisPart) -> PartResponse:
    return PartResponse(
        id=part.id,
        student_id=part.student_id,
        name=part.name,
        position=part.position,
        due_on=part.due_on,
    )


class FragmentResponse(BaseModel):
    """A fragment. Its text is never sent back wholesale, as with a version."""

    id: uuid.UUID
    student_id: uuid.UUID
    part_id: uuid.UUID
    round_number: int
    received_on: date
    question: str | None
    filename: str | None
    format: str
    pages: int
    char_count: int
    preview: str
    has_file: bool
    purged_at: datetime | None
    review_action_id: uuid.UUID | None
    verdict: str | None
    feedback: str | None
    feedback_at: datetime | None
    created_at: datetime


def fragment_response(fragment: ThesisFragment) -> FragmentResponse:
    return FragmentResponse(
        id=fragment.id,
        student_id=fragment.student_id,
        part_id=fragment.part_id,
        round_number=fragment.round_number,
        received_on=fragment.received_on,
        question=fragment.question,
        filename=fragment.filename,
        format=fragment.format,
        pages=fragment.pages,
        char_count=fragment.char_count,
        preview=fragment.preview,
        has_file=fragment.has_file,
        purged_at=fragment.purged_at,
        review_action_id=fragment.review_action_id,
        verdict=str(fragment.verdict) if fragment.verdict else None,
        feedback=fragment.feedback,
        feedback_at=fragment.feedback_at,
        created_at=fragment.created_at,
    )


class FragmentFeedbackRequest(BaseModel):
    verdict: FragmentVerdict
    feedback: str | None = Field(default=None, max_length=20000)
    # The run the text started from, when the promoter worked from its draft.
    source_action_id: uuid.UUID | None = None
    next_due_on: date | None = None


class PartEntryResponse(PartResponse):
    rounds: int
    state: str


def part_entry_response(entry: PartEntry) -> PartEntryResponse:
    return PartEntryResponse(
        **part_response(entry.part).model_dump(),
        rounds=entry.rounds,
        state=str(entry.state),
    )


class FragmentEntryResponse(FragmentResponse):
    part_name: str
    summary: str | None
    review: ActionResponse | None


def fragment_entry_response(entry: FragmentEntry) -> FragmentEntryResponse:
    return FragmentEntryResponse(
        **fragment_response(entry.fragment).model_dump(),
        part_name=entry.part_name,
        summary=entry.summary,
        review=action_response(entry.review) if entry.review else None,
    )


class TimelineEventResponse(BaseModel):
    kind: Literal["fragment", "note", "draft"]
    on: date
    fragment: FragmentEntryResponse | None = None
    note: MeetingNoteResponse | None = None
    draft: DraftResponse | None = None


def timeline_event_response(event: TimelineEvent) -> TimelineEventResponse:
    if event.fragment is not None:
        return TimelineEventResponse(
            kind="fragment",
            on=event.on,
            fragment=fragment_entry_response(event.fragment),
        )
    if event.note is not None:
        return TimelineEventResponse(
            kind="note", on=event.on, note=note_response(event.note)
        )
    if event.draft is None:  # pragma: no cover — one of the three is always set
        raise ValueError("A timeline event holds nothing")
    return TimelineEventResponse(
        kind="draft", on=event.on, draft=draft_response(event.draft)
    )


class TimelineResponse(BaseModel):
    parts: list[PartEntryResponse]
    events: list[TimelineEventResponse]


def timeline_response(timeline: WorkTimeline) -> TimelineResponse:
    return TimelineResponse(
        parts=[part_entry_response(p) for p in timeline.parts],
        events=[timeline_event_response(e) for e in timeline.events],
    )


class FragmentAwaitingResponse(BaseModel):
    fragment_id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    part_name: str
    round_number: int
    received_on: date


def fragment_awaiting_response(item: FragmentAwaiting) -> FragmentAwaitingResponse:
    return FragmentAwaitingResponse(
        fragment_id=item.fragment_id,
        student_id=item.student_id,
        student_name=item.student_name,
        part_name=item.part_name,
        round_number=item.round_number,
        received_on=item.received_on,
    )


class PartOverdueResponse(BaseModel):
    part_id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    part_name: str
    due_on: date


def part_overdue_response(item: PartOverdue) -> PartOverdueResponse:
    return PartOverdueResponse(
        part_id=item.part_id,
        student_id=item.student_id,
        student_name=item.student_name,
        part_name=item.part_name,
        due_on=item.due_on,
    )


class DashboardSummaryResponse(BaseModel):
    active_students: int
    without_topic: int
    actions_in_progress: int
    awaiting_input: list[ActionInProgressResponse]
    recent_activity: list[RecentActivityResponse]
    awaiting_feedback: list[FragmentAwaitingResponse]
    overdue_parts: list[PartOverdueResponse]


def action_in_progress_response(item: ActionInProgress) -> ActionInProgressResponse:
    return ActionInProgressResponse(
        id=item.action.id,
        student_id=item.action.student_id,
        student_name=item.student_name,
        action_type=str(item.action.action_type),
        status=str(item.action.status),
        created_at=item.action.created_at,
        updated_at=item.action.updated_at,
    )


def dashboard_summary_response(summary: DashboardSummary) -> DashboardSummaryResponse:
    return DashboardSummaryResponse(
        active_students=summary.active_students,
        without_topic=summary.without_topic,
        actions_in_progress=summary.actions_in_progress,
        awaiting_input=[action_in_progress_response(a) for a in summary.awaiting_input],
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
        awaiting_feedback=[
            fragment_awaiting_response(f) for f in summary.awaiting_feedback
        ],
        overdue_parts=[part_overdue_response(p) for p in summary.overdue_parts],
    )


# ---------- model catalog ----------


class ModelCatalogResponse(BaseModel):
    """The model a promoter's key for each provider runs on."""

    byok: dict[str, str]


class DemoSeedResponse(BaseModel):
    """Which demo students were added, and which were already there."""

    created: list[str]
    skipped: list[str]
