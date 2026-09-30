"""Crossref — does a cited work exist, and what does its record say.

Crossref is the DOI registry for most of the journal literature. Two calls:
`search` matches a whole reference string (``query.bibliographic`` is built
for exactly that — "Laibson, D. (1997). Golden eggs…" in, the article out),
and `lookup` resolves a DOI. Free and keyless; with ``CROSSREF_MAILTO`` set,
requests go to the "polite pool", which is faster and rate-limited less.

Only bibliographic entries leave the machine — author, year, title, venue.
Never the thesis text.

OpenAlex would also do, but meters its API per request; Crossref does not.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import httpx
import structlog

from src.infrastructure.settings import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_BASE_URL = "https://api.crossref.org"
_FIELDS = "DOI,title,issued,author,container-title,type,score"


class CrossrefUnavailableError(RuntimeError):
    """Crossref did not answer; nothing can be said about the reference."""


@dataclass(frozen=True)
class Work:
    """One Crossref record, trimmed to what a reference is checked against."""

    doi: str
    title: str
    year: int | None
    authors: tuple[str, ...]
    venue: str
    kind: str
    score: float

    def describe(self) -> str:
        """One line, for the agent to read."""
        authors = ", ".join(self.authors[:3]) or "?"
        return (
            f"doi:{self.doi} | {self.year or '?'} | {authors} | {self.title}"
            f" | {self.venue or '-'} | {self.kind} | score {self.score:.0f}"
        )


def _first(value: Any) -> str:  # noqa: ANN401 — Crossref's JSON
    if isinstance(value, list) and value:
        return str(cast(list[Any], value)[0])
    return ""


def _year(item: dict[str, Any]) -> int | None:
    parts: Any = item.get("issued", {}).get("date-parts") or [[None]]
    try:
        return int(parts[0][0])
    except (TypeError, ValueError, IndexError):
        return None


def _work(item: dict[str, Any]) -> Work:
    authors = cast(list[dict[str, Any]], item.get("author") or [])
    return Work(
        doi=str(item.get("DOI", "")),
        title=_first(item.get("title")),
        year=_year(item),
        authors=tuple(str(a.get("family") or a.get("name") or "") for a in authors),
        venue=_first(item.get("container-title")),
        kind=str(item.get("type", "")),
        score=float(item.get("score") or 0.0),
    )


class CrossrefClient:
    """Thin synchronous client — the worker is synchronous."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        headers = {"User-Agent": "Corvus thesis mentoring (bibliography check)"}
        if settings.crossref_mailto:
            headers["User-Agent"] += f" mailto:{settings.crossref_mailto}"
        self._client = client or httpx.Client(
            base_url=_BASE_URL, headers=headers, timeout=settings.crossref_timeout
        )

    def search(self, reference: str, rows: int = 3) -> list[Work]:
        """The closest records to a reference string, best first."""
        data = self._get(
            "/works",
            {"query.bibliographic": reference, "rows": rows, "select": _FIELDS},
        )
        items = cast(list[dict[str, Any]], data.get("message", {}).get("items", []))
        return [_work(i) for i in items]

    def lookup(self, doi: str) -> Work | None:
        """The record for a DOI, or None when Crossref has no such DOI."""
        doi = doi.strip().removeprefix("https://doi.org/").removeprefix("doi:")
        try:
            data = self._get(f"/works/{doi}", {})
        except CrossrefUnavailableError as exc:
            if "404" in str(exc):
                return None
            raise
        return _work(cast(dict[str, Any], data.get("message", {})))

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._client.get(path, params=params)
            response.raise_for_status()
            return cast(dict[str, Any], response.json())
        except httpx.HTTPError as exc:
            logger.warning("crossref_request_failed", path=path, error=str(exc))
            raise CrossrefUnavailableError(str(exc)) from exc
