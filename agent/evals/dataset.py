"""Eval cases: synthetic theses with the defects planted in them written down.

Each case is a directory under ``evals/cases/`` holding ``thesis.md`` (the
text a promoter would upload) and ``case.json`` (what a good review of it has
to find, and what it must not invent).

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

from src.application.guidelines import load_guidelines
from src.domain.analysis import FindingSeverity

CASES_DIR = Path(__file__).parent / "cases"

# The length rule of the real documents, and what it becomes for a condensed
# thesis. Replaced verbatim, so a change to the document fails loudly (see
# `condensed_guidelines`) instead of silently judging 8 kB against 80.
_LENGTH_RULES = {
    "80,000 – 130,000 characters": "7,000 – 20,000 characters",
    "Length significantly below 80,000 characters": (
        "Length significantly below 7,000 characters"
    ),
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

    def context(self) -> dict[str, Any]:
        """The action context `app` would assemble for this thesis.

        ``guidelines`` is filled in here, so the task's retrieval step — which
        needs Postgres and an embedding model — is skipped exactly as it is
        when `app` sends a guideline set's text along.
        """
        return {
            "text": self.text,
            "metadata": self.metadata,
            "thesis_type": self.thesis_type,
            "review_tone": self.metadata.get("review_tone", "auto"),
            "guidelines": condensed_guidelines(self.thesis_type),
        }


def condensed_guidelines(thesis_type: str) -> str:
    """The real requirements, with the length rule scaled to a condensed thesis."""
    text = load_guidelines(thesis_type)
    for original, condensed in _LENGTH_RULES.items():
        if original in text:
            text = text.replace(original, condensed)
    if "80,000" in text:
        raise ValueError(
            f"The {thesis_type} requirements mention 80,000 characters in a "
            "rule this eval does not know how to scale — update _LENGTH_RULES."
        )
    return text


def load_case(directory: Path) -> EvalCase:
    """Read one case directory."""
    raw = cast(
        dict[str, Any], json.loads((directory / "case.json").read_text("utf-8"))
    )
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
