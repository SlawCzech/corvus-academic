"""The shape of a rubric: four sections, whatever the regulation looked like.

Every university writes its regulation in its own order and its own
documents. A rubric is Corvus's reading of it, and it always has the same
four `## ` sections, so each analysis gets the part it judges by and an
admin knows where to look. Text before the first section — a title, where
the rubric was read from — is for people; no action is given it.

A section's heading is its identity: the parser matches the exact text.
"""

from dataclasses import dataclass
from enum import StrEnum


class RubricSection(StrEnum):
    """The four sections, by the key they travel under to `agent`."""

    ELEMENTS = "elements"
    FORMAL = "formal"
    MERIT = "merit"
    SEVERITY = "severity"


HEADINGS: dict[RubricSection, str] = {
    RubricSection.ELEMENTS: "Elementy pracy",
    RubricSection.FORMAL: "Wymogi formalne",
    RubricSection.MERIT: "Co praca ma wykazać",
    RubricSection.SEVERITY: "Waga uchybień",
}

_BY_HEADING = {heading: section for section, heading in HEADINGS.items()}


class RubricShapeError(ValueError):
    """A rubric whose sections are not exactly the four, each once."""


@dataclass(frozen=True)
class RubricSections:
    """A rubric split into its sections, each without its heading."""

    elements: str
    formal: str
    merit: str
    severity: str

    def to_dict(self) -> dict[str, str]:
        return {
            str(RubricSection.ELEMENTS): self.elements,
            str(RubricSection.FORMAL): self.formal,
            str(RubricSection.MERIT): self.merit,
            str(RubricSection.SEVERITY): self.severity,
        }


def parse_rubric(markdown: str) -> RubricSections:
    """Split a rubric into its four sections.

    Raises RubricShapeError naming what is missing, repeated, unknown or
    empty — the message an admin reads when a draft will not publish.
    """
    found: dict[RubricSection, list[str]] = {}
    current: RubricSection | None = None
    for line in markdown.splitlines():
        if line.startswith("## "):
            heading = line[3:].strip()
            section = _BY_HEADING.get(heading)
            if section is None:
                raise RubricShapeError(
                    f"Unknown rubric section {heading!r}; the sections are: "
                    + ", ".join(HEADINGS.values())
                )
            if section in found:
                raise RubricShapeError(f"Rubric section {heading!r} appears twice")
            found[section] = []
            current = section
        elif current is not None:
            found[current].append(line)

    missing = [HEADINGS[s] for s in RubricSection if s not in found]
    if missing:
        raise RubricShapeError("Rubric is missing sections: " + ", ".join(missing))
    bodies = {s: "\n".join(lines).strip() for s, lines in found.items()}
    empty = [HEADINGS[s] for s, body in bodies.items() if not body]
    if empty:
        raise RubricShapeError("Rubric sections are empty: " + ", ".join(empty))
    return RubricSections(
        elements=bodies[RubricSection.ELEMENTS],
        formal=bodies[RubricSection.FORMAL],
        merit=bodies[RubricSection.MERIT],
        severity=bodies[RubricSection.SEVERITY],
    )
