"""Domain entities for thesis review and scoring."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class Score:
    """Points awarded for a single evaluation criterion."""

    criteria: str
    points: int
    max_points: int

    def percentage(self) -> float:
        """Return score as a percentage; 0.0 when max_points is zero."""
        if self.max_points == 0:
            return 0.0
        return self.points / self.max_points * 100.0


@dataclass(frozen=True)
class Review:
    """Complete review of a thesis, immutable after generation."""

    review_id: UUID
    thesis_id: UUID
    scores: list[Score]
    summary: str
    recommendation: str

    def total_percentage(self) -> float:
        """Return overall score as a percentage across all criteria."""
        total_points = sum(s.points for s in self.scores)
        total_max = sum(s.max_points for s in self.scores)
        if total_max == 0:
            return 0.0
        return total_points / total_max * 100.0