"""Checking findings against the thesis, and against each other — no model.

Two failure modes a promoter notices first and forgives last:

- **A finding about text that is not there.** The model "quotes" a sentence
  the student never wrote. Every finding now carries a verbatim quote, and a
  quote that cannot be found in the thesis sinks its finding.
- **The same defect, twice.** The review's analyses run in parallel and never
  see each other; two of them describing one problem makes it weigh double in
  the review. Findings from different analyses that rest on the same passage,
  or say the same thing, are merged into the most severe of them.

Plain string work on purpose: deterministic, instant, and testable to the
character. What it cannot catch — a real quote under a wrong claim — is left
to the evals to measure, not to another model to guess at.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from src.domain.analysis import Finding, FindingSeverity

# Everything but letters and digits is noise for matching: quotes, dashes,
# commas and line breaks are exactly what a model changes when it "copies".
_NON_WORD = re.compile(r"[^\w%]+")
# A model's ellipsis — "…", "...", "[...]" — joins pieces that are each verbatim.
_ELLIPSIS = re.compile(r"\[?(?:\.\.\.|…)\]?")

# Below this many words a fragment is too short to prove anything either way
# ("Wstęp", "H1"): it is checked, but a miss is not a sign of invention.
_MIN_WORDS = 3
# A near-verbatim quote — a word inflected, a typo fixed — still shares most of
# its word trigrams with the passage it came from; an invented one shares few.
_FUZZY_TRIGRAMS = 0.6
# Two findings whose descriptions share this share of word stems say the same
# thing. Deliberately high: merging two different defects loses one outright,
# while leaving a duplicate only makes one weigh double.
_SAME_DESCRIPTION = 0.5
# Stems, crudely: Polish inflects endings, so "hipotezy", "hipotez" and
# "hipotezach" should meet at "hipot".
_STEM = 5

_RANK = {
    FindingSeverity.MINOR: 1,
    FindingSeverity.MAJOR: 2,
    FindingSeverity.CRITICAL: 3,
}


def normalize(text: str) -> str:
    """Lower-cased words separated by single spaces."""
    return " ".join(_NON_WORD.sub(" ", text.lower()).split())


def _trigrams(words: Sequence[str]) -> set[tuple[str, str, str]]:
    return {(words[i], words[i + 1], words[i + 2]) for i in range(len(words) - 2)}


class ThesisText:
    """A thesis, normalised once and searched many times."""

    def __init__(self, text: str) -> None:
        self._flat = f" {normalize(text)} "
        self._trigrams = _trigrams(self._flat.split())

    def contains(self, quote: str) -> bool:
        """Whether every piece of the quote is in the thesis, near verbatim."""
        pieces = [normalize(p) for p in _ELLIPSIS.split(quote)]
        pieces = [p for p in pieces if p]
        if not pieces:
            return True  # an empty quote claims nothing
        return all(self._has_piece(p) for p in pieces)

    def _has_piece(self, piece: str) -> bool:
        if f" {piece} " in self._flat:
            return True
        words = piece.split()
        if len(words) < _MIN_WORDS:
            return True  # too short to call an invention
        found = _trigrams(words) & self._trigrams
        return len(found) / max(1, len(words) - 2) >= _FUZZY_TRIGRAMS


def _stems(text: str) -> set[str]:
    return {w[:_STEM] for w in normalize(text).split() if len(w) >= 4}


def _overlap[T](a: set[T], b: set[T]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def same_problem(a: Finding, b: Finding) -> bool:
    """Whether two findings from different analyses describe one defect.

    Findings of one analysis are never merged here: its prompt already asks
    for one finding per problem, and two findings it chose to keep apart are
    more likely two problems than one.
    """
    if a.source == b.source:
        return False
    if a.quote and b.quote:
        qa, qb = normalize(a.quote), normalize(b.quote)
        if qa and qb and (qa in qb or qb in qa):
            return True
        if _overlap(_trigrams(qa.split()), _trigrams(qb.split())) >= 0.5:
            return True
    return _overlap(_stems(a.description), _stems(b.description)) >= _SAME_DESCRIPTION


@dataclass(frozen=True)
class Verification:
    """What checking the findings kept, and what it threw away and why."""

    kept: list[Finding]
    ungrounded: list[Finding]
    merged: list[Finding]

    def summary(self) -> dict[str, object]:
        """For the stored result: counts, and what was dropped, readable."""
        return {
            "kept": len(self.kept),
            "ungrounded": [
                {
                    "source": str(f.source or ""),
                    "description": f.description,
                    "quote": f.quote,
                }
                for f in self.ungrounded
            ],
            "merged": len(self.merged),
        }


def verify_findings(findings: Sequence[Finding], thesis: str) -> Verification:
    """Drop findings whose quote is not in the thesis, then merge duplicates.

    Order is kept: the first finding of a merged group stands in its place,
    carrying the group's highest severity.
    """
    text = ThesisText(thesis)
    grounded: list[Finding] = []
    ungrounded: list[Finding] = []
    for finding in findings:
        (grounded if text.contains(finding.quote) else ungrounded).append(finding)

    kept: list[Finding] = []
    merged: list[Finding] = []
    for finding in grounded:
        twin = next((k for k in kept if same_problem(k, finding)), None)
        if twin is None:
            kept.append(finding)
            continue
        if _RANK[finding.severity] > _RANK[twin.severity]:
            # The more severe reading wins, in the place the first one held.
            kept[kept.index(twin)] = finding
            merged.append(twin)
        else:
            merged.append(finding)
    return Verification(kept=kept, ungrounded=ungrounded, merged=merged)
