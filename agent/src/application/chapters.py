"""Cutting a thesis body into chapters, from the map `app` computed — no model.

The review's analyses each read a 30-thousand-character prefix of the thesis.
That is the introduction and a chapter or two; a results chapter on page 40
and the conclusions that are supposed to follow from it are never in the same
prompt. The coherence check reads the whole body instead, one chapter at a
time: each chapter is digested on its own (the map step, in parallel), and one
node reads the digests side by side (the reduce step).

Chapters come from the document map's headings. Numbered headings are grouped
by their first number — "2.1", "2.2" and "2.3" are chapter 2 — because that is
the part of a Polish thesis's numbering the outline reliably sees ("Rozdział 2"
lines are not headings to it). The introduction and the conclusions are left
out: the coherence node reads those two whole, since they are what the
chapters are checked against.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

# Big enough for a chapter of a bachelor's thesis in one call; a longer one is
# cut into parts rather than truncated — a digest of half a chapter reads as a
# digest of the chapter.
_CHUNK_CHARS = 14000
# More parts than this and the fan-out costs more than it reveals: adjacent
# parts are merged until the count fits.
_MAX_CHUNKS = 10
# How much of the introduction and the conclusions the coherence node reads.
_FRAME_CHARS = 9000

_NUMBER = re.compile(r"^\s*(\d{1,2})[.\s]")
# Headings that are not body chapters: front matter, the frame the chapters
# are checked against, and back matter.
_NOT_BODY = {
    "toc",
    "abstract",
    "keywords",
    "introduction",
    "conclusions",
    "bibliography",
    "attachments",
}


@dataclass(frozen=True)
class Chapter:
    """One part of the body, as the digest step reads it."""

    title: str
    text: str


def _sections(document_map: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = document_map.get("sections")
    if not isinstance(raw, list):
        return []
    sections = [
        cast(Mapping[str, Any], s)
        for s in cast(list[Any], raw)
        if isinstance(s, Mapping)
    ]
    return sorted(sections, key=lambda s: int(s.get("start") or 0))


def _body_bounds(
    sections: Sequence[Mapping[str, Any]], length: int
) -> tuple[int, int] | None:
    """From the last introduction heading to the bibliography after it.

    The last one, because the table of contents names the introduction too.
    """
    intros = [s for s in sections if s.get("canonical") == "introduction"]
    if not intros:
        return None
    start = int(intros[-1].get("start") or 0)
    end = next(
        (
            int(s.get("start") or 0)
            for s in sections
            if s.get("canonical") in ("bibliography", "attachments")
            and int(s.get("start") or 0) > start
        ),
        length,
    )
    return start, end


def _group_key(section: Mapping[str, Any]) -> str:
    canonical = section.get("canonical")
    if canonical:
        return str(canonical)
    number = _NUMBER.match(str(section.get("title") or ""))
    return f"chapter-{number.group(1)}" if number else str(section.get("title"))


def split_chapters(text: str, document_map: Mapping[str, Any]) -> list[Chapter]:
    """The body chapters of a thesis, in order, each small enough to digest."""
    sections = _sections(document_map)
    bounds = _body_bounds(sections, len(text))
    if bounds is None:
        return []
    body_start, body_end = bounds
    inside = [s for s in sections if body_start <= int(s.get("start") or 0) < body_end]

    # Each heading runs to the next heading, whatever kind that is.
    spans: list[tuple[Mapping[str, Any], int, int]] = []
    for index, section in enumerate(inside):
        start = int(section.get("start") or 0)
        end = (
            int(inside[index + 1].get("start") or 0)
            if index + 1 < len(inside)
            else body_end
        )
        spans.append((section, start, end))

    groups: list[tuple[str, str, int, int]] = []  # key, title, start, end
    for section, start, end in spans:
        if section.get("canonical") in _NOT_BODY:
            continue
        key = _group_key(section)
        if groups and groups[-1][0] == key and groups[-1][3] == start:
            last = groups[-1]
            groups[-1] = (key, last[1], last[2], end)
        else:
            groups.append((key, str(section.get("title") or "").strip(), start, end))

    chapters: list[Chapter] = []
    for _, title, start, end in groups:
        body = text[start:end].strip()
        if not body:
            continue
        parts = [body[i : i + _CHUNK_CHARS] for i in range(0, len(body), _CHUNK_CHARS)]
        for n, part in enumerate(parts, start=1):
            label = title if len(parts) == 1 else f"{title} (część {n}/{len(parts)})"
            chapters.append(Chapter(title=label, text=part))

    while len(chapters) > _MAX_CHUNKS:
        chapters = _merge_smallest_neighbours(chapters)
    return chapters


def _merge_smallest_neighbours(chapters: list[Chapter]) -> list[Chapter]:
    """Merge the adjacent pair with the least text between them."""
    sizes = [
        len(a.text) + len(b.text) for a, b in zip(chapters, chapters[1:], strict=False)
    ]
    i = sizes.index(min(sizes))
    merged = Chapter(
        title=f"{chapters[i].title} — {chapters[i + 1].title}",
        text=f"{chapters[i].text}\n\n{chapters[i + 1].text}",
    )
    return [*chapters[:i], merged, *chapters[i + 2 :]]


def frame(text: str, document_map: Mapping[str, Any], canonical: str) -> str:
    """The introduction or the conclusions, up to the next heading.

    The last heading of that kind: the table of contents names both.
    """
    sections = _sections(document_map)
    found = [s for s in sections if s.get("canonical") == canonical]
    if not found:
        return ""
    start = int(found[-1].get("start") or 0)
    following = [
        int(s.get("start") or 0) for s in sections if int(s.get("start") or 0) > start
    ]
    end = min(following) if following else len(text)
    return text[start:end].strip()[:_FRAME_CHARS]
