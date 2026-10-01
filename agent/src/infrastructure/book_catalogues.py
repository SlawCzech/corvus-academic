"""Library catalogues — does a cited book exist.

Crossref is a registry of DOIs, which is to say of journal articles: of a
bibliography's Polish monographs it knows almost none, and of the classics
mostly their reviews. Books live in library catalogues. Two, both free and
keyless:

- the National Library of Poland (data.bn.org.pl) — the legal-deposit
  catalogue, so nearly every book published in Poland, and the foreign ones
  the library holds;
- Open Library (openlibrary.org) — the Internet Archive's catalogue, for
  books published anywhere.

As with Crossref, only what a reference says of itself is sent — a title and
an author's surname. Never the thesis text.

Records come back as `Work`, the shape the matching rules already compare a
reference against; a book has no DOI, and its publisher stands in as venue.
"""

from __future__ import annotations

from typing import Any, cast

import httpx

from src.infrastructure.crossref import Work
from src.infrastructure.paced_http import Pace, get_json
from src.infrastructure.settings import settings

_BN_URL = "https://data.bn.org.pl"
_OPEN_LIBRARY_URL = "https://openlibrary.org"
_USER_AGENT = "Corvus thesis mentoring (bibliography check)"

# Neither states a limit in its responses. The National Library answers in
# a tenth of a second; Open Library asks unidentified clients to keep to
# about one request a second.
_BN_PACE = Pace(interval=0.2)
_OPEN_LIBRARY_PACE = Pace(interval=1.0)


def _year(value: Any) -> int | None:  # noqa: ANN401 — the catalogues' JSON
    try:
        return int(str(value)[:4])
    except (TypeError, ValueError):
        return None


def _headers() -> dict[str, str]:
    agent = _USER_AGENT
    if settings.crossref_mailto:
        agent += f" mailto:{settings.crossref_mailto}"
    return {"User-Agent": agent}


def main_title(title: str) -> str:
    """A catalogue title without its subtitle and statement of responsibility.

    ISBD punctuation: ``Title : subtitle / by Somebody``. A reference in a
    thesis usually gives the title alone, so that is what is compared.
    """
    return title.split(" / ")[0].split(" : ")[0].strip(" /:.")


class NationalLibraryClient:
    """The catalogue of the National Library of Poland."""

    name = "Biblioteka Narodowa"

    def __init__(
        self, client: httpx.Client | None = None, pace: Pace | None = None
    ) -> None:
        self._pace = pace or _BN_PACE
        self._client = client or httpx.Client(
            base_url=_BN_URL, headers=_headers(), timeout=settings.crossref_timeout
        )

    def search(self, title: str, author: str = "", rows: int = 5) -> list[Work]:
        """Records whose title and author contain the given words."""
        params: dict[str, Any] = {"title": title, "limit": rows}
        if author:
            params["author"] = author
        data = get_json(
            self._client,
            self._pace,
            "/api/institutions/bibs.json",
            params,
            source="national_library",
        )
        return [
            Work(
                doi="",
                title=main_title(str(b.get("title") or "")),
                year=_year(b.get("publicationYear")),
                # "Hagen, William W. (1942- )" — the surname is what a
                # reference is sure to carry.
                authors=tuple(
                    a for a in [str(b.get("author") or "").split(",")[0].strip()] if a
                ),
                venue=str(b.get("publisher") or "").strip(" ,"),
                kind=str(b.get("kind") or "book"),
                score=0.0,
            )
            for b in cast(list[dict[str, Any]], data.get("bibs") or [])
        ]


class OpenLibraryClient:
    """Open Library's search — books published anywhere."""

    name = "Open Library"

    def __init__(
        self, client: httpx.Client | None = None, pace: Pace | None = None
    ) -> None:
        self._pace = pace or _OPEN_LIBRARY_PACE
        self._client = client or httpx.Client(
            base_url=_OPEN_LIBRARY_URL,
            headers=_headers(),
            timeout=settings.crossref_timeout,
        )

    def search(self, title: str, author: str = "", rows: int = 5) -> list[Work]:
        """Works whose title and author match."""
        params: dict[str, Any] = {
            "title": title,
            "limit": rows,
            "fields": "title,author_name,first_publish_year,publisher",
        }
        if author:
            params["author"] = author
        data = get_json(
            self._client, self._pace, "/search.json", params, source="open_library"
        )
        works: list[Work] = []
        for doc in cast(list[dict[str, Any]], data.get("docs") or []):
            names = cast(list[Any], doc.get("author_name") or [])
            publishers = cast(list[Any], doc.get("publisher") or [])
            works.append(
                Work(
                    doi="",
                    title=str(doc.get("title") or ""),
                    year=_year(doc.get("first_publish_year")),
                    # "William W. Hagen" — again the surname.
                    authors=tuple(str(n).split()[-1] for n in names if str(n).split()),
                    venue=str(publishers[0]) if publishers else "",
                    kind="book",
                    score=0.0,
                )
            )
        return works
