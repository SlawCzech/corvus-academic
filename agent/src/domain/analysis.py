"""Domain entities for thesis analysis."""

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID


class FindingSeverity(StrEnum):
    """Severity level of a single analysis finding."""

    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


class FindingSource(StrEnum):
    """Which analysis raised a finding.

    The review's three analyses run in parallel and cannot see each other's
    results, so each owns a separate scope. The source says whose scope a
    finding fell in — and makes an overlap countable instead of anecdotal.
    """

    STRUCTURE = "structure"
    METHODOLOGY = "methodology"
    REQUIREMENTS = "requirements"
    # Read across the whole body: do the conclusions follow from the results,
    # are the hypotheses answered, do the chapters contradict each other.
    COHERENCE = "coherence"


class ReviewTone(StrEnum):
    """Tone style for the generated thesis review."""

    AUTO = "auto"
    ENTHUSIASTIC = "enthusiastic"
    COMMENDABLE = "commendable"
    POSITIVE = "positive"
    DIPLOMATIC = "diplomatic"
    RESERVED = "reserved"
    NEGATIVE = "negative"


class ThesisType(StrEnum):
    """Type of thesis being evaluated."""

    BACHELOR = "bachelor"
    MASTER_ARTICLE = "master_article"


@dataclass(frozen=True)
class Finding:
    """A single observation about the thesis, immutable once created."""

    section: str
    description: str
    severity: FindingSeverity
    suggestion: str
    # None only for findings built outside the analysis nodes (tests,
    # payloads stored before the field existed).
    source: FindingSource | None = None
    # The passage of the thesis the finding rests on, verbatim; "" when the
    # defect is that something is absent.
    quote: str = ""


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
