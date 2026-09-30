"""Checking a bibliography against Crossref — the part that needs no model.

Most references settle without judgement: Crossref's best match has the same
title, year and first author, or the entry is a web page that Crossref was
never going to know. Only what is left — no confident match — goes to the
agent, which can search again with other queries, resolve a DOI, and tell a
Polish monograph Crossref does not index from an "article" in an
international journal that nobody can find.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from src.application.grounding import normalize
from src.infrastructure.crossref import Work

# The whole list, up to a point: a bibliography is rarely past 15k characters,
# and past this the extraction call gets slow for no gain.
_SECTION_CHARS = 25000
_URL = re.compile(r"https?://|www\.", re.IGNORECASE)
_DOI = re.compile(r"10\.\d{4,9}/\S+", re.IGNORECASE)
# Share of the record's title words the reference must contain.
_TITLE_MATCH = 0.8

VERIFIED = "verified"
MISMATCH = "mismatch"
NOT_INDEXED = "not_indexed"
SUSPICIOUS = "suspicious"
WEBSITE = "website"
UNCHECKED = "unchecked"
UNRESOLVED = "unresolved"  # only between the two steps, never in the output


@dataclass(frozen=True)
class Check:
    """What was established about one reference, and how."""

    status: str
    note: str = ""
    doi: str = ""


def bibliography_section(text: str, document_map: Mapping[str, Any]) -> str:
    """The bibliography, from its heading to the next named section.

    The last bibliography heading: the table of contents names it too.
    """
    raw = document_map.get("sections")
    sections = [
        cast(Mapping[str, Any], s)
        for s in (cast(list[Any], raw) if isinstance(raw, list) else [])
        if isinstance(s, Mapping)
    ]
    found = [s for s in sections if s.get("canonical") == "bibliography"]
    if not found:
        return ""
    start = int(found[-1].get("start") or 0)
    after = [
        int(s.get("start") or 0)
        for s in sections
        if s.get("canonical") and int(s.get("start") or 0) > start
    ]
    end = min(after) if after else len(text)
    return text[start:end].strip()[:_SECTION_CHARS]


def is_website(entry: str) -> bool:
    """A web page cited by URL — netography, which Crossref does not hold."""
    return bool(_URL.search(entry)) and not _DOI.search(entry)


def doi_in(entry: str) -> str:
    """A DOI written into the reference itself, if there is one."""
    found = _DOI.search(entry)
    return found.group(0).rstrip(".,;") if found else ""


def _title_matches(work: Work, entry: str) -> bool:
    words = [w for w in normalize(work.title).split() if len(w) >= 3]
    if not words:
        return False
    flat = f" {normalize(entry)} "
    return sum(f" {w} " in flat for w in words) / len(words) >= _TITLE_MATCH


def _author_matches(work: Work, entry: str) -> bool:
    if not work.authors or not work.authors[0]:
        return True  # institutional or anonymous record: nothing to compare
    return normalize(work.authors[0]) in normalize(entry)


def match(entry: str, year: int | None, works: Sequence[Work]) -> Check:
    """Settle a reference from Crossref's candidates, or leave it unresolved."""
    for work in works:
        if not _title_matches(work, entry):
            continue
        same_year = year is None or work.year is None or abs(work.year - year) <= 1
        if same_year and _author_matches(work, entry):
            return Check(VERIFIED, doi=work.doi)
        differences: list[str] = []
        if not same_year:
            differences.append(f"rok {work.year} zamiast {year}")
        if not _author_matches(work, entry):
            differences.append(f"pierwszy autor: {work.authors[0]}")
        return Check(
            MISMATCH,
            note="Crossref zna tę pracę, ale: " + ", ".join(differences),
            doi=work.doi,
        )
    return Check(UNRESOLVED)
