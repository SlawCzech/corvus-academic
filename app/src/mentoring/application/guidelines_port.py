"""What mentoring needs from the guideline catalog, and nothing more.

A port rather than an import: mentoring's use cases depend on this protocol,
and only ``infrastructure/guidelines_adapter.py`` knows the catalog exists —
the same one-way seam as identity, kept at the edge of the context.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class GuidelineRubric:
    """The rubric in force for a set, and the version it came from."""

    version_id: UUID
    rubric_md: str


class GuidelineSource(Protocol):
    async def thesis_type_of(self, set_id: UUID) -> str | None:
        """The thesis type of a set a promoter can pick, or None if there is
        no such set or nothing in it has been published."""
        ...

    async def current_rubric(self, set_id: UUID) -> GuidelineRubric | None:
        """The published rubric actions are judged against today, if any."""
        ...

    async def first_set_for(self, thesis_type: str) -> UUID | None:
        """A published set for this kind of thesis, if the catalog has one —
        what a student gets when nobody has picked a set for them."""
        ...
