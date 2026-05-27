"""Domain entity representing an extracted document."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Document:
    """Immutable value object for a parsed document."""

    text: str
    pages: int
    format: str
