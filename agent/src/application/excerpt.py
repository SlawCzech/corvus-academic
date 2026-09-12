"""What a node is shown of a thesis, and what it is told about the rest.

A thesis is tens of thousands of characters and every node gets a prefix of
it. That is survivable; what is not survivable is a node treating the end of
its excerpt as the end of the work, which is how a chapter sitting on page 18
becomes a CRITICAL finding that it was never written.

So every node that reads thesis text goes through here, and gets three things
in one block: a map of the whole document computed in `app` without a model,
the excerpt it is actually allowed to read, and the rule that separates the
two. One place to change when the budgets or the wording change.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

# The bibliography goes in whole when it falls outside the excerpt. Half of it
# is worse than none: a model asked for the number of foreign-language sources
# answers from what it was shown, and a partial list reads as a short one.
_BIBLIOGRAPHY_CHARS = 20000

_RULES = """\
## What this excerpt does and does not prove

The document map above was computed from the COMPLETE thesis; the excerpt is \
a fragment. A section listed in the map EXISTS in the thesis, whether or not \
it appears below.

- NEVER report a section as missing, absent or unwritten when the map lists it.
- NEVER judge the thesis incomplete because the excerpt ends mid-sentence.
- NEVER count sources, tables or chapters from the excerpt — use the counts \
in the map.
- Judge length against the body length in the map, never against the extracted \
total: the total includes the title page, declarations, contents and \
bibliography, which length requirements exclude.
- Report only defects you can see in the text you were given."""


def _format_map(document_map: Mapping[str, Any]) -> str:
    """Render the outline `app` computed over the whole document."""
    raw = document_map.get("sections")
    sections = cast(Sequence[Mapping[str, Any]], raw) if isinstance(raw, list) else ()
    lines = [
        "## Document map (computed from the COMPLETE thesis, not from the excerpt)",
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
        lines.append(f"Bibliography entries counted: {entries}.")

    if sections:
        lines.append("")
        lines.append("Sections present, in order (start — length):")
        lines += [
            f"- {section.get('title')} "
            f"(char {int(section.get('start') or 0):,} — "
            f"{int(section.get('char_count') or 0):,} chars)"
            for section in sections
        ]
    return "\n".join(lines)


def _bibliography_tail(text: str, document_map: Mapping[str, Any], shown: int) -> str:
    """The bibliography, when the excerpt stopped short of it."""
    raw = document_map.get("sections")
    sections = cast(Sequence[Mapping[str, Any]], raw) if isinstance(raw, list) else ()
    found = next((s for s in sections if s.get("canonical") == "bibliography"), None)
    if found is None:
        return ""
    start = int(found.get("start") or 0)
    if start < shown:
        return ""  # already inside the excerpt
    end = min(start + _BIBLIOGRAPHY_CHARS, len(text))
    return (
        f"\n\n## Bibliography (characters {start:,}–{end:,} of the thesis)\n\n"
        f"{text[start:end]}"
    )


def render_document_block(
    ctx: Mapping[str, Any],
    head_chars: int,
    include_bibliography: bool = True,
) -> str:
    """Return the thesis block for a node's prompt: map, excerpt, and rules."""
    text = str(ctx.get("text", ""))
    raw_map = ctx.get("document_map")
    document_map: Mapping[str, Any] = (
        cast(Mapping[str, Any], raw_map) if isinstance(raw_map, dict) else {}
    )

    shown = min(head_chars, len(text))
    truncated = shown < len(text)
    header = (
        f"## Thesis excerpt (characters 0–{shown:,} of {len(text):,}; "
        "the remainder is NOT shown)"
        if truncated
        else f"## Thesis, complete ({len(text):,} characters)"
    )

    parts: list[str] = []
    if document_map:
        parts.append(_format_map(document_map))
    parts.append(f"{header}\n\n{text[:shown]}")
    if truncated and include_bibliography and document_map:
        tail = _bibliography_tail(text, document_map, shown)
        if tail:
            parts.append(tail.strip())
    if truncated:
        parts.append(_RULES if document_map else _RULES.split("\n\n", 2)[-1])
    return "\n\n".join(parts)
