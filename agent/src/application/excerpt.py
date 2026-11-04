"""What a node is shown of a thesis: all of it, with the numbers code counted.

A hosted model reads the whole thesis. Its context holds a work many times
over, and every cut is a place where the model judges a thesis it has not
read. What goes with the text is what a model does badly by itself: the body
length that length requirements are about, and the bibliography count, both
computed in `app` without a model.

Every node that reads thesis text goes through here.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast


def _format_map(document_map: Mapping[str, Any]) -> str:
    """Render the counts `app` computed over the whole document.

    A model reads headings for itself, but it does not count characters, and
    it miscounts a bibliography.
    """
    lines = [
        "## Counted from the thesis by code — use these numbers, do not recount",
        "",
    ]

    body = document_map.get("body_chars")
    if isinstance(body, int):
        lines.append(
            f"Length of the thesis body: {body:,} characters "
            "(abstract through the last chapter — this is the number length "
            "requirements are about)."
        )
    lines.append(
        f"Total extracted, including title page, declarations, contents and "
        f"bibliography: {int(document_map.get('total_chars') or 0):,} characters."
    )

    entries = document_map.get("bibliography_entries")
    if isinstance(entries, int):
        web = document_map.get("bibliography_web_entries")
        lines.append(
            f"Bibliography entries counted: {entries}"
            + (f", of which {web} give a web address." if web else ".")
        )
    return "\n".join(lines)


def render_document_block(ctx: Mapping[str, Any]) -> str:
    """Return the thesis block for a node's prompt: the counts, then the text."""
    text = str(ctx.get("text", ""))
    raw_map = ctx.get("document_map")
    document_map: Mapping[str, Any] = (
        cast(Mapping[str, Any], raw_map) if isinstance(raw_map, dict) else {}
    )

    parts: list[str] = []
    if document_map:
        parts.append(_format_map(document_map))
    parts.append(f"## Thesis, complete ({len(text):,} characters)\n\n{text}")
    return "\n\n".join(parts)
