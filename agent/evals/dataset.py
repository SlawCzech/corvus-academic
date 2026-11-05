"""Eval cases: synthetic theses with the defects planted in them written down.

Each case is a directory under ``evals/cases/`` holding ``thesis.md`` (the
text a promoter would upload) and ``case.json`` (what a good review of it has
to find, and what it must not invent).

Each case may carry ``document_map.json`` — the map `app` would send with the
text, made with `app`'s ``scripts/document_map.py``. Regenerate it when a
thesis changes: ``make eval-maps``.

The theses are condensed — 7–12 thousand characters instead of 80–130 — so a
whole case fits in one node's excerpt and a run takes minutes, not hours. The
requirements the nodes are judged against are adjusted to match: the length
rule is scaled down, everything else is the real bachelor document. Without
that, every case would be one planted defect plus "far too short", and the
eval would measure nothing but that.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from src.domain.analysis import FindingSeverity

CASES_DIR = Path(__file__).parent / "cases"

# The rubrics `app` seeds into the catalog — the same files, so an eval judges
# against what a promoter's student is judged against. Evals run from a
# checkout of the whole repository (`make eval`), where they sit side by side.
_RUBRICS_DIR = (
    Path(__file__).resolve().parents[2] / "app" / "scripts" / "seed_data" / "guidelines"
)

# Their `## ` headings and the keys `app` sends each section under
# (`app/src/guidelines/domain/rubric.py`).
_SECTION_KEYS = {
    "Elementy pracy": "elements",
    "Wymogi formalne": "formal",
    "Co praca ma wykazać": "merit",
    "Waga uchybień": "severity",
}

# The thresholds `app` seeds for a bachelor thesis, with the length scaled to
# a condensed case. The rubric names no numbers, so the thresholds are all
# there is to scale.
_CONDENSED_THRESHOLDS = {
    "min_sources": 25,
    "min_foreign_sources": 4,
    "min_body_chars": 5_000,
    "max_body_chars": 20_000,
}


@dataclass(frozen=True)
class ExpectedIssue:
    """One planted defect a good review names."""

    id: str
    issue: str
    severity: FindingSeverity


@dataclass(frozen=True)
class EvalCase:
    """One synthetic thesis and what its review has to get right."""

    id: str
    description: str
    thesis_type: str
    text: str
    metadata: dict[str, Any]
    expected: tuple[ExpectedIssue, ...]
    must_not_flag: tuple[str, ...]
    acceptable_recommendations: tuple[str, ...]
    # The map `app` computes over the whole text (scripts/document_map.py in
    # `app`): what the prefix-reading nodes are told about the rest, and
    # what the coherence check cuts into chapters.
    document_map: dict[str, Any] | None = None

    def context(self) -> dict[str, Any]:
        """The action context `app` would assemble for this thesis.

        ``guidelines`` is the seeded rubric, by section, as `app` sends it;
        ``thresholds`` carry the length scaled to the condensed case.
        """
        context: dict[str, Any] = {
            "text": self.text,
            "metadata": self.metadata,
            "thesis_type": self.thesis_type,
            "review_tone": self.metadata.get("review_tone", "auto"),
            "guidelines": rubric_sections(self.thesis_type),
            "thresholds": _CONDENSED_THRESHOLDS,
        }
        if self.document_map is not None:
            context["document_map"] = self.document_map
        return context


def rubric_sections(thesis_type: str) -> dict[str, str]:
    """The seeded rubric for a thesis type, split as `app` sends it."""
    text = (_RUBRICS_DIR / f"{thesis_type}.md").read_text("utf-8")
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = _SECTION_KEYS[line[3:].strip()]
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return {key: "\n".join(lines).strip() for key, lines in sections.items()}


def load_case(directory: Path) -> EvalCase:
    """Read one case directory."""
    raw = cast(dict[str, Any], json.loads((directory / "case.json").read_text("utf-8")))
    expected = cast(list[dict[str, str]], raw["expected"])
    return EvalCase(
        id=str(raw["id"]),
        description=str(raw.get("description", "")),
        thesis_type=str(raw["thesis_type"]),
        text=(directory / "thesis.md").read_text("utf-8"),
        metadata=cast(dict[str, Any], raw["metadata"]),
        expected=tuple(
            ExpectedIssue(
                id=item["id"],
                issue=item["issue"],
                severity=FindingSeverity(item["severity"]),
            )
            for item in expected
        ),
        must_not_flag=tuple(cast(list[str], raw.get("must_not_flag", []))),
        acceptable_recommendations=tuple(
            cast(list[str], raw.get("acceptable_recommendations", []))
        ),
        document_map=(
            cast(
                dict[str, Any],
                json.loads((directory / "document_map.json").read_text("utf-8")),
            )
            if (directory / "document_map.json").exists()
            else None
        ),
    )


def load_cases(only: list[str] | None = None) -> list[EvalCase]:
    """Every case, or the ones named, in a stable order."""
    directories = sorted(p for p in CASES_DIR.iterdir() if (p / "case.json").exists())
    cases = [load_case(d) for d in directories]
    if only:
        unknown = set(only) - {c.id for c in cases}
        if unknown:
            raise ValueError(f"Unknown eval cases: {sorted(unknown)}")
        cases = [c for c in cases if c.id in only]
    return cases
