"""Context assembly — what the agent is told about a student, per action.

One function per action type, each taking domain objects and returning a
plain dict. Deliberately pure and separate from the service that fetches the
rows: this is the seam where a future chat agent picks the same functions up
as tools, and it keeps "what the model sees" reviewable in isolation.

Assembly happens here, in `app`, and never in `agent`: the agent gets its
context whole at dispatch, so a Celery worker's job never depends on `app`
being up, and no node needs a database.
"""

from collections.abc import Sequence
from typing import Any

from src.mentoring.domain.draft import ThesisDraft
from src.mentoring.domain.student import MeetingNote, Student

# How much history is worth sending. Small on purpose — the point is to give
# the model the state of play, not the student's whole file.
_MAX_NOTES = 3


class MissingContextError(Exception):
    """The student's record does not yet hold what this action needs.

    Raised before anything is dispatched — asking for defence questions
    without a thesis, or for a progress check with only one version, is a
    state problem, not a model problem.
    """


def _thesis_metadata(student: Student) -> dict[str, Any]:
    """The metadata block the review nodes expect."""
    return {
        "author": student.full_name,
        "title": student.current_topic or "",
        "year": student.created_at.year,
        "field_of_study": student.field_of_study,
        "thesis_type": str(student.thesis_type),
    }


def assemble_propose_topic_context(
    student: Student,
    recent_notes: Sequence[MeetingNote] = (),
    detail: str | None = None,
) -> dict[str, Any]:
    """Build the context for a topic proposal.

    Needs no document and no guidelines — the student record, the last few
    meeting notes and whatever the promoter typed are enough, which is why
    this is the first action to run end-to-end.
    """
    return {
        "field_of_study": student.field_of_study,
        "thesis_type": str(student.thesis_type),
        "current_topic": student.current_topic,
        "detail": detail,
        "recent_notes": [n.content for n in recent_notes[:_MAX_NOTES]],
    }


def assemble_evaluate_methodology_context(
    student: Student,
    latest_draft: ThesisDraft | None,
    detail: str | None = None,
) -> dict[str, Any]:
    """Build the context for a methodology review of the current version."""
    if latest_draft is None:
        raise MissingContextError(
            "Methodology can only be assessed once a draft has been uploaded"
        )
    return {
        "text": latest_draft.text,
        "thesis_type": str(student.thesis_type),
        "current_topic": student.current_topic,
        "version_number": latest_draft.version_number,
        "detail": detail,
    }


def assemble_check_progress_context(
    student: Student,
    latest_drafts: Sequence[ThesisDraft],
    detail: str | None = None,
) -> dict[str, Any]:
    """Build the context for comparing the two newest versions.

    Takes exactly the two rows the action needs — newest first — rather than
    the student's whole upload history.
    """
    if len(latest_drafts) < 2:
        raise MissingContextError(
            "Progress needs two uploaded versions to compare"
        )
    current, previous = latest_drafts[0], latest_drafts[1]
    return {
        "current_text": current.text,
        "current_version": current.version_number,
        "previous_text": previous.text,
        "previous_version": previous.version_number,
        "current_topic": student.current_topic,
        "detail": detail,
    }


def assemble_draft_meeting_note_context(
    student: Student,
    recent_notes: Sequence[MeetingNote] = (),
    detail: str | None = None,
) -> dict[str, Any]:
    """Build the context for writing up a meeting from rough points."""
    if not (detail or "").strip():
        raise MissingContextError(
            "Rough notes from the meeting are what this action writes up"
        )
    return {
        "detail": detail,
        "current_topic": student.current_topic,
        "recent_notes": [n.content for n in recent_notes[:_MAX_NOTES]],
    }


def assemble_defence_questions_context(
    student: Student,
    latest_draft: ThesisDraft | None,
    detail: str | None = None,
) -> dict[str, Any]:
    """Build the context for preparing defence questions."""
    if latest_draft is None:
        raise MissingContextError(
            "Defence questions are asked about a thesis — upload one first"
        )
    return {
        "text": latest_draft.text,
        "current_topic": student.current_topic,
        "field_of_study": student.field_of_study,
        "thesis_type": str(student.thesis_type),
        "version_number": latest_draft.version_number,
        "detail": detail,
    }


def assemble_generate_review_context(
    student: Student,
    latest_draft: ThesisDraft | None,
    detail: str | None = None,
    review_tone: str = "auto",
) -> dict[str, Any]:
    """Build the context for the full four-node review.

    `guidelines` is deliberately absent: the requirements document is static
    data `agent` owns, and it loads it itself from `thesis_type`.
    """
    if latest_draft is None:
        raise MissingContextError("There is no thesis to review yet")
    return {
        "text": latest_draft.text,
        "metadata": _thesis_metadata(student),
        "thesis_type": str(student.thesis_type),
        "review_tone": review_tone,
        "version_number": latest_draft.version_number,
        "detail": detail,
    }
