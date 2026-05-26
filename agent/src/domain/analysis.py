"""Domain entities for thesis analysis."""

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID


class FindingSeverity(StrEnum):
    """Severity level of a single analysis finding."""

    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


@dataclass(frozen=True)
class Finding:
    """A single observation about the thesis, immutable once created."""

    section: str
    description: str
    severity: FindingSeverity
    suggestion: str


@dataclass
class ThesisAnalysis:
    """Collected findings and requirement flags for one thesis."""

    thesis_id: UUID
    findings: list[Finding] = field(default_factory=list[Finding])
    requirements: list[str] = field(default_factory=list[str])

    def critical_count(self) -> int:
        """Return the number of CRITICAL findings."""
        return sum(1 for f in self.findings if f.severity == FindingSeverity.CRITICAL)

    def is_ready_to_submit(self) -> bool:
        """Return True when no CRITICAL findings remain."""
        return self.critical_count() == 0
