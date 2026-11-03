"""Cutting a thesis body into chapters, from the map `app` computed — no model.

The review's analyses each read a 30-thousand-character prefix of the thesis.
That is the introduction and a chapter or two; a results chapter on page 40
and the conclusions that are supposed to follow from it are never in the same
prompt. The coherence check reads the whole body instead, one chapter at a
time: each chapter is digested on its own (the map step, in parallel), and one
node reads the digests side by side (the reduce step).

Chapters come from the document map's headings. Numbered headings are grouped
by their first number — "Rozdział 2", "2.1", "2.2" and "2.3" are chapter 2.
The introduction and the conclusions are left out: the coherence node reads
those two whole, since they are what the chapters are checked against.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

# More parts than this and the fan-out costs more than it reveals: adjacent
# parts are merged until the count fits.
_MAX_CHUNKS = 10

# "2.3. Formy prawne" — numbered below the chapter level.
_SUBSECTION = re.compile(r"^\s*\d{1,2}\.\d")
_NUMBER = re.compile(r"^\s*(?:(?:rozdział|chapter)\s+)?(\d{1,2})[.:\s]", re.IGNORECASE)
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


def _chapter_number(title: str) -> str | None:
    """The chapter a heading belongs to: "Rozdział 2", "2. …" and "2.3. …" → 2."""
    number = _NUMBER.match(title)
    return number.group(1) if number else None


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

    # A chapter opens at a heading that is not a subsection — "Rozdział 2…",
    # "2. …", or a named section such as "Wyniki badań" — and takes the
    # numbered subsections under it, whatever they are called: "4.1. Metodyka
    # badań" is part of chapter 4, and "Wyniki badań" followed by "3.1." is
    # one chapter, not a twelve-character one and another.
    groups: list[tuple[str, str | None, int, int]] = []  # title, number, start, end
    open_chapter = False
    for section, start, end in spans:
        if section.get("canonical") in _NOT_BODY:
            open_chapter = False
            continue
        title = str(section.get("title") or "").strip()
        number = _chapter_number(title)
        if open_chapter and _SUBSECTION.match(title) and groups[-1][3] == start:
            head, opened_as, opened_at, _ = groups[-1]
            if opened_as in (None, number):
                groups[-1] = (head, number, opened_at, end)
                continue
        groups.append((title, number, start, end))
        open_chapter = True

    chapters: list[Chapter] = []
    for title, _, start, end in groups:
        body = text[start:end].strip()
        if not body:
            continue
        chapters.append(Chapter(title=title, text=body))

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
    return text[start:end].strip()
