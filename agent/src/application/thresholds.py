"""The numeric requirements, compared with the thesis by code.

A model does not count characters and it miscounts a bibliography, so the
comparison happens here. Whether a miss is a defect does not: a length is only
suggested, a project thesis may have fewer sources, and a web address may sit
on a journal article. So this hands the requirements node facts and leaves the
finding and its severity to the model, ADR 0020.

Only the requirements node reads this. The block appears only when `app` sent
thresholds, so a run without a guideline set reads as it always did.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

_RULE = """\
Read these as facts: use the numbers, do not recount them and do not contradict \
them. They are not findings. Whether a shortfall is a defect, and how severe, \
follows from the requirements document: a suggested length is not a hard limit, \
and a project thesis may justify fewer sources. A number within its requirement \
is not a finding."""


def _sources(minimum: int, document_map: Mapping[str, Any]) -> str:
    entries = document_map.get("bibliography_entries")
    if not isinstance(entries, int):
        return (
            f"- Sources: at least {minimum} required. Code found no bibliography "
            "to count."
        )
    web = document_map.get("bibliography_web_entries")
    web = web if isinstance(web, int) else 0
    if entries < minimum:
        standing = "BELOW the minimum"
    elif entries - web < minimum:
        standing = "meets the minimum only if the entries with a web address count"
    else:
        standing = "meets the minimum"
    note = (
        f" {web} of them give a web address, so they may be netography, which "
        "does not count towards this minimum."
        if web
        else ""
    )
    required = f"at least {minimum} required"
    return f"- Sources: {entries} entries, {required}: {standing}.{note}"


def _foreign_sources(minimum: int) -> str:
    # Telling a language from a bibliography entry is reading, not counting.
    return (
        f"- Foreign-language sources: at least {minimum} required. Not counted by "
        "code: count them yourself in the bibliography, leaving netography out."
    )


def _length(
    minimum: int | None, maximum: int | None, document_map: Mapping[str, Any]
) -> str:
    wanted = (
        f"{minimum or 0:,}–{maximum:,}"
        if maximum is not None
        else f"at least {minimum or 0:,}"
    )
    body = document_map.get("body_chars")
    if not isinstance(body, int):
        return f"- Length: {wanted} characters. Code could not measure the body."
    if minimum is not None and body < minimum:
        standing = "below the range"
    elif maximum is not None and body > maximum:
        standing = "above the range"
    else:
        standing = "within the range"
    return f"- Length of the body: {body:,} characters, against {wanted}: {standing}."


def _mapping(value: object) -> Mapping[str, Any]:
    return cast(Mapping[str, Any], value) if isinstance(value, dict) else {}


def render_threshold_block(ctx: Mapping[str, Any]) -> str:
    """Return the comparison for the prompt, or "" when no thresholds came."""
    thresholds = _mapping(ctx.get("thresholds"))
    document_map = _mapping(ctx.get("document_map"))

    min_sources = thresholds.get("min_sources")
    min_foreign = thresholds.get("min_foreign_sources")
    min_body = thresholds.get("min_body_chars")
    max_body = thresholds.get("max_body_chars")

    lines: list[str] = []
    if min_sources is not None:
        lines.append(_sources(min_sources, document_map))
    if min_foreign is not None:
        lines.append(_foreign_sources(min_foreign))
    if min_body is not None or max_body is not None:
        lines.append(_length(min_body, max_body, document_map))
    if not lines:
        return ""
    return "\n".join(
        ["## Numeric requirements, compared by code", "", *lines, "", _RULE]
    )
