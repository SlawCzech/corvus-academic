"""Domain entities for the pieces of a thesis handed in while it is written.

A fragment is not a version of the thesis (`draft.py`): the actions that read
"the latest version" must never see one, so the two are kept apart. See
ADR 0014.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import UUID

# What a timeline shows when there is no AI summary to show.
_PREVIEW_CHARS = 400


class FragmentVerdict(StrEnum):
    """What the promoter said about a fragment. Only ever set by the promoter."""

    ON_TRACK = "on_track"
    NEEDS_CHANGES = "needs_changes"
    NEEDS_ADDITIONS = "needs_additions"


class PartState(StrEnum):
    """Where a part of the thesis stands. Derived, never stored."""

    NOT_SUBMITTED = "not_submitted"
    AWAITING_FEEDBACK = "awaiting_feedback"
    ON_TRACK = "on_track"
    NEEDS_CHANGES = "needs_changes"
    NEEDS_ADDITIONS = "needs_additions"


@dataclass
class ThesisPart:
    """A part of the thesis: "Rozdział 1", "Część literaturowa".

    Named by the promoter while uploading, or ahead of time to hold a
    deadline. `due_on` goes away when a fragment of this part arrives.
    """

    id: UUID
    student_id: UUID
    name: str
    position: int
    due_on: date | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("part name must not be empty")


@dataclass
class ThesisFragment:
    """One round of a part: what the student handed in, and what they heard.

    Like a `ThesisDraft`, a purged fragment keeps its row and loses its text
    and file. The verdict and the feedback are the promoter's, not the
    student's work, and stay.
    """

    id: UUID
    student_id: UUID
    part_id: UUID
    round_number: int
    received_on: date
    text: str | None
    format: str
    uploaded_by: UUID
    question: str | None = None
    filename: str | None = None
    pages: int = 0
    # None for pasted text; hash and size outlive the file, as on a draft.
    file_id: UUID | None = None
    file_sha256: str | None = None
    file_size: int | None = None
    # Stored rather than derived, so a purged fragment still reports it.
    char_count: int = 0
    purged_at: datetime | None = None
    # The latest AI run on this fragment.
    review_action_id: UUID | None = None
    verdict: FragmentVerdict | None = None
    feedback: str | None = None
    feedback_at: datetime | None = None
    # The run whose draft the promoter started from; None for their own words.
    feedback_source_action_id: UUID | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if self.round_number < 1:
            raise ValueError("round_number must start at 1")
        if self.purged_at is None and not (self.text or "").strip():
            raise ValueError("fragment text must not be empty")
        if self.text is not None:
            self.char_count = len(self.text)

    @property
    def is_purged(self) -> bool:
        """Whether the text and file have been removed under retention."""
        return self.purged_at is not None

    @property
    def has_file(self) -> bool:
        """Whether the original upload can still be downloaded."""
        return self.file_id is not None

    @property
    def awaits_feedback(self) -> bool:
        """Whether the promoter still owes the student an answer."""
        return self.verdict is None

    @property
    def content(self) -> str:
        """The text. Asking a purged fragment for it is a bug."""
        if self.text is None:
            raise ValueError(f"Fragment {self.id} has been purged")
        return self.text

    @property
    def preview(self) -> str:
        """First few hundred characters, for a timeline without a summary."""
        text = (self.text or "").strip()
        return text[:_PREVIEW_CHARS] + ("…" if len(text) > _PREVIEW_CHARS else "")

    def record_feedback(
        self,
        verdict: FragmentVerdict,
        feedback: str | None,
        at: datetime,
        source_action_id: UUID | None = None,
    ) -> None:
        """Set what the promoter told the student. Saving again corrects it."""
        self.verdict = verdict
        self.feedback = (feedback or "").strip() or None
        self.feedback_at = at
        self.feedback_source_action_id = source_action_id

    def purge(self, at: datetime) -> None:
        """Drop the text and the file reference; keep everything else."""
        self.text = None
        self.file_id = None
        self.purged_at = at


def part_state(latest: ThesisFragment | None) -> PartState:
    """A part stands where its latest round left it."""
    if latest is None:
        return PartState.NOT_SUBMITTED
    if latest.verdict is None:
        return PartState.AWAITING_FEEDBACK
    return PartState(str(latest.verdict))
