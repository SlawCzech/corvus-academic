"""The university's rubric, cut to what one analysis judges by.

`app` sends the rubric of the student's guideline set in four sections
(`app/src/guidelines/domain/rubric.py`, ADR 0024). Each node takes the
sections its question needs: the requirements check reads the elements, the
formal rules and the severity rules; the methodology and the review read the
elements and what the thesis must show. A node never sees the severity rules
it does not apply, nor the formal rules outside its scope.

A version published before rubrics had sections arrives as one string; it
goes to every node whole, as all rubrics did before.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

ELEMENTS = "elements"
FORMAL = "formal"
MERIT = "merit"
SEVERITY = "severity"

_TITLES = {
    ELEMENTS: "Required elements of the thesis",
    FORMAL: "Formal requirements",
    MERIT: "What the thesis must show",
    SEVERITY: "Severity of violations (Corvus's reading, not the regulation's)",
}

REQUIREMENTS_SECTIONS = (ELEMENTS, FORMAL, SEVERITY)
METHODOLOGY_SECTIONS = (ELEMENTS, MERIT)
REVIEW_SECTIONS = (ELEMENTS, MERIT)


def render_guidelines(ctx: Mapping[str, Any], sections: tuple[str, ...]) -> str:
    """The chosen sections under their titles, or "" when none came."""
    guidelines = ctx.get("guidelines")
    if isinstance(guidelines, str):
        return guidelines
    if not isinstance(guidelines, dict):
        return ""
    by_key = cast(dict[str, Any], guidelines)
    parts = [
        f"### {_TITLES[key]}\n{text}"
        for key in sections
        if isinstance(text := by_key.get(key), str) and text.strip()
    ]
    return "\n\n".join(parts)
