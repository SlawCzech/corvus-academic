"""Domain entities for the mentoring bounded context.

Pure Python — no SQLAlchemy, no FastAPI, no imports from other contexts.
``promotor_id`` is a plain UUID pointing at ``identity.users``; the reference
is deliberately not modelled as a relation, matching the existing
cross-context precedent in ``agent``'s ``AnalysisModel.user_id``.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID


class ThesisType(StrEnum):
    """Type of thesis the student is writing.

    Values match ``agent``'s ``ThesisType`` and the frontend's ``thesis_type``
    field verbatim: the same string is handed to the guideline loader once
    actions run against a student, so the two vocabularies must not drift.
    """

    BACHELOR = "bachelor"
    MASTER_ARTICLE = "master_article"


class StudentStatus(StrEnum):
    """Where the student is in the supervision lifecycle."""

    ACTIVE = "active"
    GRADUATED = "graduated"
    ARCHIVED = "archived"


def _require_text(value: str, field_name: str) -> str:
    """Return the stripped value, or raise if it is blank."""
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be empty")
    return stripped


@dataclass
class Student:
    """A student supervised by one promoter across the whole thesis lifecycle."""

    id: UUID
    promotor_id: UUID
    full_name: str
    field_of_study: str
    thesis_type: ThesisType
    index_number: str | None = None
    current_topic: str | None = None
    current_topic_set_at: datetime | None = None
    status: StudentStatus = StudentStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.full_name = _require_text(self.full_name, "full_name")
        self.field_of_study = _require_text(self.field_of_study, "field_of_study")
        if self.index_number is not None:
            self.index_number = _require_text(self.index_number, "index_number")

    @property
    def has_topic(self) -> bool:
        """Return True once a thesis topic has been settled on."""
        return self.current_topic is not None

    def is_supervised_by(self, promotor_id: UUID) -> bool:
        """Return True if the given promoter supervises this student."""
        return self.promotor_id == promotor_id

    def set_topic(self, topic: str, at: datetime | None = None) -> None:
        """Record the accepted thesis topic and when it was accepted.

        The only piece of state denormalized onto the student — everything
        else stays queryable as history through ``agent_actions``.
        """
        self.current_topic = _require_text(topic, "topic")
        self.current_topic_set_at = at or datetime.now(UTC)

    def change_status(self, status: StudentStatus) -> None:
        """Move the student to another lifecycle status."""
        self.status = status


@dataclass
class MeetingNote:
    """A human-approved record of one supervision meeting.

    ``source_action_id`` carries provenance: set when the note started life as
    an AI draft (``draft_meeting_note``) that the promoter accepted, None when
    the promoter wrote it by hand.
    """

    id: UUID
    student_id: UUID
    promotor_id: UUID
    occurred_at: datetime
    content: str
    source_action_id: UUID | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.content = _require_text(self.content, "content")

    @property
    def is_ai_drafted(self) -> bool:
        """Return True if this note originated from an accepted AI draft."""
        return self.source_action_id is not None
