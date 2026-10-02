"""The range each review score may take, decided by the findings — no model.

The reviewer model was told the scale and scored a sound thesis 5/10 on a
criterion with one major finding all the same. So the scale lives here: the
model proposes the points, and they are held to the band the findings in
that criterion leave open — the same arrangement as the recommendation.
"""

from __future__ import annotations

from collections.abc import Sequence

from src.domain.analysis import Finding, FindingSeverity, FindingSource

Band = tuple[int, int]

_SCALE = 10

# The review's four criteria, in the order the prompt asks for them, and the
# analyses whose findings count towards each. The last — substantive quality —
# has no analysis of its own and answers for the whole review.
_SCOPES: tuple[frozenset[FindingSource] | None, ...] = (
    frozenset({FindingSource.STRUCTURE, FindingSource.COHERENCE}),
    frozenset({FindingSource.METHODOLOGY}),
    frozenset({FindingSource.REQUIREMENTS}),
    None,
)

# How many MAJOR findings a criterion carries before it drops to the lowest
# band a thesis without a CRITICAL finding can get.
_MAJOR_TOLERANCE = 1
_MAJOR_TOLERANCE_OVERALL = 3

_WITH_CRITICAL: Band = (0, 5)
_MANY_MAJOR: Band = (6, 7)
_SOME_MAJOR: Band = (7, 8)
_MINOR_ONLY: Band = (8, 10)


def _band(findings: Sequence[Finding], tolerance: int) -> Band:
    if any(f.severity == FindingSeverity.CRITICAL for f in findings):
        return _WITH_CRITICAL
    major = sum(1 for f in findings if f.severity == FindingSeverity.MAJOR)
    if major == 0:
        return _MINOR_ONLY
    return _SOME_MAJOR if major <= tolerance else _MANY_MAJOR


def score_bands(
    findings: Sequence[Finding], criteria: int = len(_SCOPES)
) -> list[Band]:
    """The lowest and highest points each criterion may get, on a 0–10 scale.

    A criterion past the four known ones is judged like the overall one.
    """
    bands: list[Band] = []
    for index in range(criteria):
        scope = _SCOPES[index] if index < len(_SCOPES) else None
        if scope is None:
            bands.append(_band(findings, _MAJOR_TOLERANCE_OVERALL))
        else:
            in_scope = [f for f in findings if f.source in scope]
            bands.append(_band(in_scope, _MAJOR_TOLERANCE))
    return bands


def within_band(points: int, max_points: int, band: Band) -> int:
    """``points`` moved into ``band``; untouched on any scale other than 0–10."""
    if max_points != _SCALE:
        return points
    low, high = band
    return min(max(points, low), high)
