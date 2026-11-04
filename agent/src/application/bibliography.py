"""Checking a bibliography against the catalogues — the part that needs no model.

Most references settle without judgement: a record has the same title and
first author, or the entry is a web page no catalogue was ever going to
know. Articles are looked for in Crossref; what it does not have — books,
mostly — in the library catalogues. Only what is left goes to the agent,
which can search again with other queries, resolve a DOI, and tell an old
print no catalogue indexes from an "article" in an international journal
that nobody can find.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from src.application.grounding import normalize
from src.infrastructure.crossref import Work

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
    return text[start:end].strip()


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


def _fold(text: str) -> str:
    """Without diacritics: catalogues spell Wyczański as Wyczanski, or worse."""
    decomposed = unicodedata.normalize("NFKD", text.replace("ł", "l").replace("Ł", "L"))
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _author_matches(work: Work, entry: str) -> bool:
    if not work.authors or not work.authors[0]:
        return True  # institutional or anonymous record: nothing to compare
    return normalize(_fold(work.authors[0])) in normalize(_fold(entry))


def first_surname(authors: str) -> str:
    """The first author's surname, from "Hagen, W. W." or "North, D. C., i …"."""
    return authors.split(",")[0].split(" i ")[0].strip()


def search_title(title: str) -> str:
    """A title as a catalogue wants it: no subtitle, plain hyphens."""
    main = re.split(r"[:.?!] ", title.strip())[0]
    return main.replace("–", "-").replace("—", "-").strip(" .")


def _same_year(work: Work, year: int | None) -> bool:
    return year is None or work.year is None or abs(work.year - year) <= 1


def match(
    entry: str, year: int | None, works: Sequence[Work], source: str = "Crossref"
) -> Check:
    """Settle a reference from a source's candidates, or leave it unresolved.

    `source` is named in the note when the record is not in Crossref: a DOI
    says where a work was found, a book in a library catalogue has none.

    Every candidate is looked at, not the first whose title fits: for a
    well-known book the best-scoring records are its reviews — same title,
    the reviewer as author — and the book itself comes fourth.

    A record with the title under another author is therefore not this work
    with a wrong author; it says nothing, and is passed over. A record with
    the title and the author under another year is this work in another
    edition or a reprint (Wallerstein 1974, in Crossref as the 2011 edition) —
    unless all there is is a journal article: an article has one year, and a
    reference that gives another has it wrong.
    """
    same_work = [
        w for w in works if _title_matches(w, entry) and _author_matches(w, entry)
    ]
    found_in = "" if source == "Crossref" else f"Katalog: {source}."
    for work in same_work:
        if _same_year(work, year):
            return Check(VERIFIED, note=found_in, doi=work.doi)
    if not same_work:
        return Check(UNRESOLVED)
    work = same_work[0]
    one_article = all(w.kind == "journal-article" for w in same_work) and (
        len({w.year for w in same_work}) == 1
    )
    if one_article:
        return Check(
            MISMATCH,
            note=f"Crossref zna tę pracę, ale: rok {work.year} zamiast {year}",
            doi=work.doi,
        )
    where = "W Crossref" if source == "Crossref" else f"Katalog: {source},"
    return Check(
        VERIFIED,
        note=f"{where} jako wydanie lub przedruk z {work.year} r.",
        doi=work.doi,
    )
