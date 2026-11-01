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


def _optional_text(value: str | None) -> str | None:
    """Return the stripped value, or None if there is nothing in it."""
    return (value or "").strip() or None


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
    # When supervision ended (graduated or archived) — where the retention
    # clock for the student's thesis files starts.
    closed_at: datetime | None = None
    # The version the promoter accepted as final, and when.
    accepted_draft_id: UUID | None = None
    draft_accepted_at: datetime | None = None
    # The university requirements this thesis is judged against — an id in the
    # guideline catalog, another bounded context.
    guideline_set_id: UUID | None = None
    # What the promoter agreed with the student: what the thesis is about and
    # what it sets out to do. Optional, and context for the model, not a
    # checklist: see ADR 0015.
    research_area: str | None = None
    research_aim: str | None = None
    # One thesis reviewed once, nobody supervised: see ADR 0017.
    is_one_off: bool = False

    def __post_init__(self) -> None:
        self.full_name = _require_text(self.full_name, "full_name")
        self.field_of_study = _require_text(self.field_of_study, "field_of_study")
        if self.index_number is not None:
            self.index_number = _require_text(self.index_number, "index_number")
        self.research_area = _optional_text(self.research_area)
        self.research_aim = _optional_text(self.research_aim)

    @classmethod
    def one_off(
        cls,
        id: UUID,
        promotor_id: UUID,
        full_name: str,
        field_of_study: str,
        thesis_type: ThesisType,
        at: datetime | None = None,
        research_area: str | None = None,
        research_aim: str | None = None,
    ) -> "Student":
        """A thesis to review once, with nobody to supervise.

        Born archived: nothing about it is ongoing, and the retention clock
        starts with the upload rather than with a status change that nobody
        would ever make.
        """
        created = at or datetime.now(UTC)
        return cls(
            id=id,
            promotor_id=promotor_id,
            full_name=full_name,
            field_of_study=field_of_study,
            thesis_type=thesis_type,
            status=StudentStatus.ARCHIVED,
            created_at=created,
            updated_at=created,
            closed_at=created,
            research_area=research_area,
            research_aim=research_aim,
            is_one_off=True,
        )

    @property
    def has_topic(self) -> bool:
        """Return True once a thesis topic has been settled on."""
        return self.current_topic is not None

    def is_supervised_by(self, promotor_id: UUID) -> bool:
        """Return True if the given promoter supervises this student."""
        return self.promotor_id == promotor_id

    def update_details(
        self,
        full_name: str | None = None,
        field_of_study: str | None = None,
    ) -> None:
        """Correct the student's name and/or field of study.

        Both are validated before either is applied, so a blank one leaves
        the student as it was.
        """
        name = _require_text(full_name, "full_name") if full_name is not None else None
        field_ = (
            _require_text(field_of_study, "field_of_study")
            if field_of_study is not None
            else None
        )
        if name is not None:
            self.full_name = name
        if field_ is not None:
            self.field_of_study = field_

    def set_index_number(self, index_number: str | None) -> None:
        """Set the index number, or clear it with ``None``."""
        self.index_number = (
            _require_text(index_number, "index_number")
            if index_number is not None
            else None
        )

    def set_research_area(self, area: str | None) -> None:
        """Set the research area, or clear it with ``None`` or blank text."""
        self.research_area = _optional_text(area)

    def set_research_aim(self, aim: str | None) -> None:
        """Set the agreed aim, or clear it with ``None`` or blank text."""
        self.research_aim = _optional_text(aim)

    def change_thesis_type(self, thesis_type: ThesisType) -> None:
        """Switch the kind of thesis the student writes.

        The guideline set is chosen per thesis type, so a real change drops
        the choice — a set for the old type would judge the thesis against
        the wrong rules.
        """
        if thesis_type is self.thesis_type:
            return
        self.thesis_type = thesis_type
        self.guideline_set_id = None

    def set_topic(self, topic: str, at: datetime | None = None) -> None:
        """Record the thesis topic and when it was settled.

        Written by hand, or by accepting a ``propose_topic`` action — the
        promoter does not need the AI to agree on a topic with the student.
        The only piece of state denormalized onto the student — everything
        else stays queryable as history through ``agent_actions``.
        """
        self.current_topic = _require_text(topic, "topic")
        self.current_topic_set_at = at or datetime.now(UTC)

    def clear_topic(self) -> None:
        """The topic is open again."""
        self.current_topic = None
        self.current_topic_set_at = None

    def change_status(self, status: StudentStatus, at: datetime | None = None) -> None:
        """Move the student to another lifecycle status.

        Leaving `active` starts the retention clock once; moving from
        `graduated` to `archived` does not restart it. Returning to `active`
        stops it.

        A one-off review has no such lifecycle: reactivating one would stop
        its clock and leave it hidden, so its thesis would never be purged.
        `promote` is the way out.
        """
        if self.is_one_off:
            raise ValueError("A one-off review has no lifecycle status")
        self.status = status
        if status is StudentStatus.ACTIVE:
            self.closed_at = None
        elif self.closed_at is None:
            self.closed_at = at or datetime.now(UTC)

    def promote(self) -> None:
        """Turn a one-off review into a student on the roster, for good."""
        if not self.is_one_off:
            raise ValueError("Only a one-off review can be promoted")
        self.is_one_off = False
        self.change_status(StudentStatus.ACTIVE)

    def accept_draft(self, draft_id: UUID, at: datetime | None = None) -> None:
        """Mark one version as the final one."""
        self.accepted_draft_id = draft_id
        self.draft_accepted_at = at or datetime.now(UTC)

    def clear_draft_acceptance(self) -> None:
        """No version is final any more — a new upload, or a change of mind."""
        self.accepted_draft_id = None
        self.draft_accepted_at = None


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
