"""Deterministic outline of an extracted thesis.

What sections a document contains is a question about the document, not a
question for a language model. Answering it here — by reading the whole text,
which nothing downstream does — is what keeps a truncated excerpt from turning
into a finding that a chapter was never written.

Headings are matched as whole lines against the section names the university
requirements use, so a line of running prose that happens to begin with
"Wyniki badań" is not mistaken for the chapter of that name.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# One entry per section the requirements documents name, with the spellings
# theses actually use. The canonical key groups the aliases; the title kept in
# the outline is whatever the document itself wrote.
_ALIASES: dict[str, tuple[str, ...]] = {
    "abstract": ("abstrakt", "streszczenie", "abstract"),
    "keywords": ("słowa kluczowe", "slowa kluczowe", "keywords"),
    "toc": ("spis treści", "spis tresci", "table of contents"),
    "introduction": ("wstęp", "wstep", "wprowadzenie", "introduction"),
    "literature": (
        "przegląd literatury",
        "przeglad literatury",
        "literature review",
    ),
    "methodology": (
        "metodyka badań",
        "metodyka badan",
        "metodologia badań",
        "metodologia badan",
        "metodyka",
        "metodologia",
        "metoda badawcza",
        "research methodology",
    ),
    "results": (
        "wyniki badań",
        "wyniki badan",
        "wyniki",
        "analiza wyników",
        "analiza wynikow",
        "results",
    ),
    "discussion": ("dyskusja", "discussion"),
    "conclusions": (
        "wnioski",
        "zakończenie",
        "zakonczenie",
        "podsumowanie",
        "conclusions",
    ),
    "bibliography": (
        "bibliografia",
        "spis literatury",
        "wykaz źródeł",
        "wykaz zrodel",
        "literatura",
        "bibliography",
        "references",
    ),
    "attachments": ("załączniki", "zalaczniki", "aneks", "appendix"),
}

_BY_ALIAS: dict[str, str] = {
    alias: canonical
    for canonical, aliases in _ALIASES.items()
    for alias in aliases
}

# A table-of-contents line: "Metodyka badań.................18".
_DOT_LEADER = re.compile(r"\.{4,}")

# "3.1. Aktywność cyfrowa" — a numbered heading, kept for the structure view.
# At most two digits per level: "180." and "104822." start bibliography
# entries, not chapters.
_NUMBERED = re.compile(r"^(\d{1,2}(?:\.\d{1,2})*)\.?\s+(\S.*)$")

# "Rozdział 2. Klub sportowy jako organizacja" — how a bachelor's thesis names
# its chapters. A title, or nothing, after the number: "Rozdział 3 zawiera
# opis…" is a sentence.
_CHAPTER = re.compile(
    r"^(?:rozdział|chapter)\s+\d{1,2}\s*[.:–-]?\s*(.*)$", re.IGNORECASE
)

# What a numbered SUBSECTION may be taken for. "4.1. Metodyka badań" is the
# methodology; "1.9. Podsumowanie" is a chapter's own summary, not the
# thesis's conclusions — and read as those, it ended the table of contents
# early and took every numbered heading of the body with it.
_SUBSECTION_KINDS = frozenset({"literature", "methodology", "results", "discussion"})

# A bibliography entry carries a year in brackets; a heading does not.
_YEAR = re.compile(r"\(\s*\d{4}[a-z]?\s*[,)]")

# The cell separator a DOCX table row is extracted with ("2004 | 19,0"). A row
# is never a heading, even one that opens with a number and a capital letter.
_TABLE_CELL_SEPARATOR = " | "

# Longest line still plausibly a heading rather than a sentence.
_MAX_HEADING_CHARS = 80

# Numbered bibliography entries: "1. Adamczyk, J., ...".
_NUMBERED_ENTRY = re.compile(r"^\s*(\d{1,3})\.\s*(.*)$")


@dataclass(frozen=True)
class Section:
    """One heading found in the document, and how much text follows it."""

    title: str
    """The heading as the document wrote it."""

    canonical: str | None
    """Which required section this is, when it is one of them."""

    start: int
    """Character offset of the heading in the extracted text."""

    char_count: int
    """Characters from this heading up to the next one."""


def _normalise(line: str) -> str:
    """Strip the decoration a heading may carry, for alias matching."""
    cleaned = line.replace("\xa0", " ").strip()
    cleaned = cleaned.strip(":.– -")
    return re.sub(r"\s+", " ", cleaned).casefold()


def _heading_at(line: str) -> tuple[str, str | None] | None:
    """Return (title, canonical) when this line is a heading, else None."""
    stripped = line.replace("\xa0", " ").strip()
    if not stripped or len(stripped) > _MAX_HEADING_CHARS:
        return None
    if _DOT_LEADER.search(stripped) or _YEAR.search(stripped):
        return None
    if _TABLE_CELL_SEPARATOR in stripped:
        return None

    canonical = _BY_ALIAS.get(_normalise(stripped))
    if canonical is not None:
        return stripped, canonical

    chapter = _CHAPTER.match(stripped)
    if chapter is not None:
        title = chapter.group(1)
        return (stripped, None) if not title or title[:1].isupper() else None

    numbered = _NUMBERED.match(stripped)
    if numbered is None or not numbered.group(2)[:1].isupper():
        return None
    # "1. Wstęp" is the introduction; "3.1. Aktywność cyfrowa" is a heading
    # under its own name.
    inner = _BY_ALIAS.get(_normalise(numbered.group(2)))
    if "." in numbered.group(1) and inner not in _SUBSECTION_KINDS:
        inner = None
    return stripped, inner


def _drop_false_headings(
    found: list[tuple[str, str | None, int]],
) -> list[tuple[str, str | None, int]]:
    """Remove numbered lines that are not chapter headings.

    Two places produce them: the table of contents, where a long title wraps
    onto a line of its own without dot leaders, and the bibliography, whose
    entries are a numbered list. Both are bounded by canonical headings, so
    the filter is positional rather than another guess at the text.
    """
    body_start = next(
        (i for i, (_, canonical, _) in enumerate(found)
         if canonical is not None and canonical != "toc"),
        0,
    )
    bibliography = next(
        (i for i, (_, canonical, _) in enumerate(found)
         if canonical == "bibliography"),
        len(found),
    )
    return [
        heading
        for index, heading in enumerate(found)
        if heading[1] is not None or body_start < index < bibliography
    ]


def _ends_toc(
    line: str, heading: tuple[str, str | None] | None, named_in_toc: set[str]
) -> bool:
    """Whether this line, read inside a table of contents, is the body instead.

    Two signs, whichever comes first: a section the contents already named
    turning up again — the body's own "Wstęp" — or a paragraph too long to be
    an entry. Dot-leader lines are entries however long they run.
    """
    if heading is not None:
        return heading[1] is not None and heading[1] in named_in_toc
    stripped = line.strip()
    return len(stripped) > _MAX_HEADING_CHARS and not _DOT_LEADER.search(stripped)


def _opens_a_chapter(title: str) -> bool:
    """A "Rozdział 2…" line, or a heading numbered at the top level ("2. …")."""
    if _CHAPTER.match(title):
        return True
    numbered = _NUMBERED.match(title)
    return numbered is not None and "." not in numbered.group(1)


def extract_outline(text: str) -> list[Section]:
    """Return the headings of a thesis, in the order they appear.

    Table-of-contents lines are skipped. Dot leaders give most of them away,
    but not all: a contents block of bare section names, without leaders or
    page numbers, reads line for line like the headings it lists. So what
    follows a "Spis treści" heading counts as contents until the body begins.
    """
    found: list[tuple[str, str | None, int]] = []
    named_in_toc: set[str] | None = None  # None: not inside a contents block
    offset = 0
    for line in text.splitlines(keepends=True):
        heading = _heading_at(line)
        if named_in_toc is not None and _ends_toc(line, heading, named_in_toc):
            named_in_toc = None
        if named_in_toc is not None:
            if heading is not None and heading[1] is not None:
                named_in_toc.add(heading[1])
        elif heading is not None:
            found.append((heading[0], heading[1], offset))
            if heading[1] == "toc":
                named_in_toc = set()
        offset += len(line)
    found = _drop_false_headings(found)

    # A named section runs until the next named section, not until its own
    # first subsection: "Wyniki badań" followed immediately by "3.1." is
    # twenty thousand characters of results, not fourteen. A new chapter ends
    # it too — "Wstęp" followed by "Rozdział 1" is the introduction, not the
    # introduction and the three chapters after it.
    section_ends = [
        start
        for title, canonical, start in found
        if canonical or _opens_a_chapter(title)
    ]

    sections: list[Section] = []
    for index, (title, canonical, start) in enumerate(found):
        if canonical is not None:
            end = next((s for s in section_ends if s > start), len(text))
        else:
            end = found[index + 1][2] if index + 1 < len(found) else len(text)
        sections.append(
            Section(
                title=title,
                canonical=canonical,
                start=start,
                char_count=end - start,
            )
        )
    return sections


def find_section(outline: list[Section], canonical: str) -> Section | None:
    """Return the longest section of the given kind, if the document has one.

    Longest rather than first: a thesis names its chapters twice — once in the
    table of contents, once where the chapter starts — and only one of those
    has the chapter under it.
    """
    matching = [s for s in outline if s.canonical == canonical]
    if not matching:
        return None
    return max(matching, key=lambda s: s.char_count)


def _entry_number(line: str) -> int | None:
    """Return the number this line opens a bibliography entry with, if it does.

    Three shapes occur in extracted PDFs, and only the first is the textbook
    one: "12. Nowak, A." , "12.Nowak, A." with the space lost, and "12." alone
    on its line with the author wrapped onto the next. What must not count is
    a wrapped line that happens to start with digits — a page range ending in
    "s. 1-13." or a DOI — so a line continuing in lower case or in digits is
    not an entry.
    """
    match = _NUMBERED_ENTRY.match(line)
    if match is None:
        return None
    rest = match.group(2).strip()
    if rest and (rest[0].islower() or rest[0].isdigit()):
        return None
    return int(match.group(1))


def count_bibliography_entries(text: str, outline: list[Section]) -> int | None:
    """Count entries in the bibliography, or None when there is no bibliography.

    Counts numbered entries first, since that is how these theses are written,
    and falls back to lines carrying a publication year.
    """
    section = find_section(outline, "bibliography")
    if section is None:
        return None
    body = text[section.start : section.start + section.char_count]
    lines = body.splitlines()[1:]  # drop the heading itself

    # Follow the numbering rather than counting every line that starts with a
    # digit: an entry wrapping onto a second line can begin with a page range
    # or a DOI, and those are numbers too. Entries run 1, 2, 3…, so only a
    # line carrying the number we are waiting for opens a new one.
    expected = 1
    for line in lines:
        if _entry_number(line) == expected:
            expected += 1
    if expected > 1:
        return expected - 1
    return sum(1 for line in lines if _YEAR.search(line))


# Where the work itself begins and ends. The length requirement counts the
# article, not the title page, the declarations, the table of contents or the
# bibliography — so a map reporting only the extracted total invites exactly
# the finding it was added to prevent, one section further along.
_BODY_START = ("abstract", "keywords", "introduction")
_BODY_END = ("bibliography", "attachments")


def body_char_count(text: str, outline: list[Section]) -> int | None:
    """Length of the thesis proper, or None when its bounds are not known."""
    start = next(
        (s.start for s in outline if s.canonical in _BODY_START), None
    )
    if start is None:
        return None
    ends = [s.start for s in outline if s.canonical in _BODY_END and s.start > start]
    return (min(ends) if ends else len(text)) - start


def outline_payload(text: str) -> dict[str, object]:
    """The document map as it travels to the agent, inside an action context."""
    outline = extract_outline(text)
    return {
        "total_chars": len(text),
        "body_chars": body_char_count(text, outline),
        "sections": [
            {
                "title": s.title,
                "canonical": s.canonical,
                "start": s.start,
                "char_count": s.char_count,
            }
            for s in outline
        ],
        "bibliography_entries": count_bibliography_entries(text, outline),
    }
