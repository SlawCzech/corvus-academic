"""Value objects for thesis metadata."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ThesisMetadata:
    """Immutable description of a submitted thesis."""

    author: str
    title: str
    year: int
    field_of_study: str