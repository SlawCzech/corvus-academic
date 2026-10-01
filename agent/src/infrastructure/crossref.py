"""Crossref — does a cited work exist, and what does its record say.

Crossref is the DOI registry for most of the journal literature. Two calls:
`search` matches a whole reference string (``query.bibliographic`` is built
for exactly that — "Laibson, D. (1997). Golden eggs…" in, the article out),
and `lookup` resolves a DOI. Free and keyless; with ``CROSSREF_MAILTO`` set,
requests go to the "polite pool", which is faster and rate-limited less.

Without it the limit is one request a second, one at a time, and a
bibliography of forty entries asked for back to back came home half
"unchecked" on 429s. So requests are paced to the limit Crossref states in
every response's headers, never overlap within a worker process, and a 429
or a 5xx is waited out and asked again before the entry is given up on.

Only bibliographic entries leave the machine — author, year, title, venue.
Never the thesis text.

OpenAlex would also do, but meters its API per request; Crossref does not.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

import httpx
import structlog

from src.infrastructure.settings import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_BASE_URL = "https://api.crossref.org"
_FIELDS = "DOI,title,issued,author,container-title,type,score"


# How long to wait before asking again after a 429 or a 5xx — unless the
# response says (Retry-After). Past the last one the entry is "unchecked".
_RETRY_WAITS = (2.0, 4.0, 8.0)
# Pace a little under the stated limit rather than exactly at it.
_MARGIN = 1.1


class CrossrefUnavailableError(RuntimeError):
    """Crossref did not answer; nothing can be said about the reference."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class Pace:
    """Keeps a process's requests to Crossref's stated rate, one at a time.

    The limit is not a constant: the public pool allows one request a second,
    the polite pool more, and every response says which applies
    (``X-Rate-Limit-Limit`` per ``X-Rate-Limit-Interval``). The first request
    goes out unpaced and teaches the rest.
    """

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.lock = threading.Lock()
        self.sleep = sleep
        self._clock = clock
        self._interval = 0.0
        self._last = float("-inf")

    def wait(self) -> None:
        """Hold until the next request is allowed. Call with the lock held."""
        delay = self._last + self._interval - self._clock()
        if delay > 0:
            self.sleep(delay)
        self._last = self._clock()

    def learn(self, headers: httpx.Headers) -> None:
        """Read the limit off a response, and space the next request by it."""
        try:
            limit = float(headers.get("x-rate-limit-limit", ""))
            interval = float(headers.get("x-rate-limit-interval", "").rstrip("s"))
        except ValueError:
            return
        if limit > 0 and interval > 0:
            self._interval = interval / limit * _MARGIN


_PACE = Pace()


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

    def __init__(
        self, client: httpx.Client | None = None, pace: Pace | None = None
    ) -> None:
        self._pace = pace or _PACE
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
            if exc.status == 404:
                return None
            raise
        return _work(cast(dict[str, Any], data.get("message", {})))

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        for wait in (*_RETRY_WAITS, None):
            try:
                with self._pace.lock:
                    self._pace.wait()
                    response = self._client.get(path, params=params)
                    self._pace.learn(response.headers)
            except httpx.HTTPError as exc:
                logger.warning("crossref_request_failed", path=path, error=str(exc))
                raise CrossrefUnavailableError("brak połączenia") from exc
            status = response.status_code
            if response.is_success:
                return cast(dict[str, Any], response.json())
            if wait is None or not (status == 429 or status >= 500):
                logger.warning("crossref_request_failed", path=path, status=status)
                reason = "limit zapytań" if status == 429 else f"HTTP {status}"
                raise CrossrefUnavailableError(reason, status)
            logger.info("crossref_retrying", path=path, status=status, wait=wait)
            self._pace.sleep(_retry_after(response) or wait)
        raise AssertionError("unreachable")  # pragma: no cover


def _retry_after(response: httpx.Response) -> float | None:
    """Seconds the server asked for, when it asked in seconds."""
    try:
        return max(0.0, float(response.headers.get("retry-after", "")))
    except ValueError:
        return None
