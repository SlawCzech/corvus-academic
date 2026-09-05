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

from src.mentoring.domain.student import MeetingNote, Student

# How much history is worth sending. Small on purpose — the point is to give
# the model the state of play, not the student's whole file.
_MAX_NOTES = 3


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
