"""Aggregate root that orchestrates the full thesis evaluation lifecycle."""

from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID

from .analysis import ThesisAnalysis
from .metadata import ThesisMetadata
from .review import Review


class EvaluationStatus(Enum):
    """Lifecycle state of a thesis evaluation."""

    UPLOADED = "uploaded"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    REVIEWED = "reviewed"
    REJECTED = "rejected"


VALID_TRANSITIONS: dict[EvaluationStatus, set[EvaluationStatus]] = {
    EvaluationStatus.UPLOADED: {EvaluationStatus.ANALYZING},
    EvaluationStatus.ANALYZING: {
        EvaluationStatus.ANALYZED,
        EvaluationStatus.REJECTED,
    },
    EvaluationStatus.ANALYZED: {EvaluationStatus.REVIEWED},
    EvaluationStatus.REVIEWED: set(),
    EvaluationStatus.REJECTED: set(),
}


@dataclass
class ThesisEvaluation:
    """Aggregate root that owns the state machine for a single evaluation."""

    id: UUID
    metadata: ThesisMetadata
    status: EvaluationStatus = field(default=EvaluationStatus.UPLOADED)
    analysis: ThesisAnalysis | None = field(default=None)
    review: Review | None = field(default=None)

    def _transition(self, target: EvaluationStatus) -> None:
        allowed = VALID_TRANSITIONS[self.status]
        if target not in allowed:
            raise ValueError(
                f"Cannot transition from {self.status.value!r} "
                f"to {target.value!r}. "
                f"Allowed: {[s.value for s in allowed]}"
            )
        self.status = target

    def start_analysis(self) -> None:
        """Move evaluation into the ANALYZING state."""
        self._transition(EvaluationStatus.ANALYZING)

    def complete_analysis(self, analysis: ThesisAnalysis) -> None:
        """Store analysis result and move to ANALYZED or REJECTED."""
        self.analysis = analysis
        if analysis.is_ready_to_submit():
            self._transition(EvaluationStatus.ANALYZED)
        else:
            self._transition(EvaluationStatus.REJECTED)

    def attach_review(self, review: Review) -> None:
        """Attach a completed review and move to REVIEWED."""
        self.review = review
        self._transition(EvaluationStatus.REVIEWED)

    def is_complete(self) -> bool:
        """Return True when the evaluation has reached a terminal state."""
        return self.status in {
            EvaluationStatus.REVIEWED,
            EvaluationStatus.REJECTED,
        }