"""What a node is shown of a thesis, and what it is told about the rest.

Two paths, decided here and nowhere else (`reading_budget`):

- **A hosted model reads the whole thesis.** Its context holds a work many
  times over, and every cut is a place where the model judges a thesis it
  has not read: a progress check that saw the first seven thousand
  characters of each version compared two title pages.
- **The local model reads an excerpt.** A thesis is tens of thousands of
  characters and its context is not. That is survivable; what is not is a
  node treating the end of its excerpt as the end of the work, which is how
  a chapter sitting on page 18 becomes a CRITICAL finding that it was never
  written. So the excerpt travels with a map of the whole document computed
  in `app` without a model, and the rule that separates the two.

Every node that reads thesis text goes through here. One place to change
when the budgets or the wording change.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from src.infrastructure.llm_factory import hosted_model_in_effect


def reading_budget(local_chars: int) -> int | None:
    """How many characters of a text a node may be shown; None for all of it.

    `local_chars` is the node's ration on the local model. On a hosted model
    there is no ration.
    """
    return None if hosted_model_in_effect() else local_chars


def within_budget(text: str, local_chars: int) -> str:
    """The text as far as the budget goes — all of it on a hosted model."""
    budget = reading_budget(local_chars)
    return text if budget is None else text[:budget]


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


def _format_map(document_map: Mapping[str, Any], with_sections: bool = True) -> str:
    """Render what `app` computed over the whole document.

    With the excerpt goes the whole outline: it is how a node knows what lies
    past the part it was shown. With the complete thesis only the counts go —
    a model reads headings for itself, but it does not count characters, and
    it miscounts a bibliography.
    """
    raw = document_map.get("sections")
    sections = (
        cast(Sequence[Mapping[str, Any]], raw)
        if with_sections and isinstance(raw, list)
        else ()
    )
    lines = [
        "## Document map (computed from the COMPLETE thesis, not from the excerpt)"
        if with_sections
        else "## Counted from the thesis by code — use these numbers, do not recount",
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
    """Return the thesis block for a node's prompt: map, text, and rules.

    `head_chars` is how much the node reads on the local model. A hosted
    model gets the thesis complete, with the map and without the rules about
    what an excerpt does not prove — there is no excerpt.
    """
    text = str(ctx.get("text", ""))
    raw_map = ctx.get("document_map")
    document_map: Mapping[str, Any] = (
        cast(Mapping[str, Any], raw_map) if isinstance(raw_map, dict) else {}
    )

    budget = reading_budget(head_chars)
    shown = len(text) if budget is None else min(budget, len(text))
    truncated = shown < len(text)
    header = (
        f"## Thesis excerpt (characters 0–{shown:,} of {len(text):,}; "
        "the remainder is NOT shown)"
        if truncated
        else f"## Thesis, complete ({len(text):,} characters)"
    )

    parts: list[str] = []
    if document_map:
        parts.append(_format_map(document_map, with_sections=truncated))
    parts.append(f"{header}\n\n{text[:shown]}")
    if truncated and include_bibliography and document_map:
        tail = _bibliography_tail(text, document_map, shown)
        if tail:
            parts.append(tail.strip())
    if truncated:
        parts.append(_RULES if document_map else _RULES.split("\n\n", 2)[-1])
    return "\n\n".join(parts)
