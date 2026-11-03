"""When a thesis version's text and file are purged.

Pure rules, no clock and no database: the sweep that applies them passes
`now` in, which is what makes the boundaries testable to the day.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from src.mentoring.domain.draft import ThesisDraft
from src.mentoring.domain.fragment import ThesisFragment
from src.mentoring.domain.student import Student


@dataclass(frozen=True)
class RetentionPolicy:
    """How long versions are kept.

    ``non_final_grace`` — versions other than the accepted one survive this
    long after the acceptance; long enough to undo a mis-click or take the
    thesis back after a reviewer returns it.
    ``after_close`` — every version survives this long after the student is
    marked graduated or archived. Corvus is a working tool, not the archive;
    the official copy lives in the university's own system.
    """

    non_final_grace: timedelta = timedelta(days=30)
    after_close: timedelta = timedelta(days=150)

    def purge_due_at(self, student: Student, draft: ThesisDraft) -> datetime | None:
        """When this version is due to be purged, or None if it is not."""
        if draft.is_purged:
            return None
        due: list[datetime] = []
        if student.closed_at is not None:
            due.append(student.closed_at + self.after_close)
        if (
            student.accepted_draft_id is not None
            and student.draft_accepted_at is not None
            and draft.id != student.accepted_draft_id
        ):
            due.append(student.draft_accepted_at + self.non_final_grace)
        return min(due) if due else None

    def fragment_purge_due_at(
        self, student: Student, fragment: ThesisFragment
    ) -> datetime | None:
        """When this fragment is due to be purged, or None if it is not.

        On the clocks of a version that is not the accepted one: a fragment is
        never the final text, so accepting a version starts its clock too.
        """
        if fragment.is_purged:
            return None
        due: list[datetime] = []
        if student.closed_at is not None:
            due.append(student.closed_at + self.after_close)
        if student.draft_accepted_at is not None:
            due.append(student.draft_accepted_at + self.non_final_grace)
        return min(due) if due else None

    def fragments_to_purge(
        self, student: Student, fragments: Sequence[ThesisFragment], now: datetime
    ) -> list[ThesisFragment]:
        """The fragments whose purge date has come."""
        return [
            f
            for f in fragments
            if (due := self.fragment_purge_due_at(student, f)) is not None
            and due <= now
        ]

    def drafts_to_purge(
        self, student: Student, drafts: Sequence[ThesisDraft], now: datetime
    ) -> list[ThesisDraft]:
        """The versions whose purge date has come."""
        return [
            d
            for d in drafts
            if (due := self.purge_due_at(student, d)) is not None and due <= now
        ]
