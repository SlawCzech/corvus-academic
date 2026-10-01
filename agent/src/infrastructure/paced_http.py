"""Asking a public catalogue politely: paced, one at a time, patient with a 429.

Crossref, the National Library and Open Library are free and keyless, and
each says — in its headers or its documentation — how often it wants to be
asked. A bibliography of forty entries sent back to back came home half
"unchecked"; so requests to one source never overlap within a worker
process, keep that source's interval, and a 429 or a 5xx is waited out and
asked again before the entry is given up on.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any, cast

import httpx
import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# How long to wait before asking again after a 429 or a 5xx — unless the
# response says (Retry-After). Past the last one the entry is "unchecked".
_RETRY_WAITS = (2.0, 4.0, 8.0)
# Pace a little under a stated limit rather than exactly at it.
_MARGIN = 1.1


class SourceUnavailableError(RuntimeError):
    """The source did not answer; nothing can be said about the reference."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class Pace:
    """Keeps a process's requests to one source to its rate, one at a time.

    ``interval`` is the spacing to start with. A source that states its limit
    in every response (Crossref: ``X-Rate-Limit-Limit`` per
    ``X-Rate-Limit-Interval`` — one a second in the public pool, more in the
    polite one) corrects it through `learn`.
    """

    def __init__(
        self,
        interval: float = 0.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.lock = threading.Lock()
        self.sleep = sleep
        self._clock = clock
        self._interval = interval
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


def get_json(
    client: httpx.Client,
    pace: Pace,
    path: str,
    params: dict[str, Any],
    *,
    source: str,
) -> dict[str, Any]:
    """GET a JSON object from `source`, paced and retried.

    Raises `SourceUnavailableError` — with the HTTP status when there was one
    — once the source has refused for the last time, or cannot be reached.
    """
    for wait in (*_RETRY_WAITS, None):
        try:
            with pace.lock:
                pace.wait()
                response = client.get(path, params=params)
                pace.learn(response.headers)
        except httpx.HTTPError as exc:
            logger.warning("source_request_failed", source=source, error=str(exc))
            raise SourceUnavailableError("brak połączenia") from exc
        status = response.status_code
        if response.is_success:
            return cast(dict[str, Any], response.json())
        if wait is None or not (status == 429 or status >= 500):
            logger.warning("source_request_failed", source=source, status=status)
            reason = "limit zapytań" if status == 429 else f"HTTP {status}"
            raise SourceUnavailableError(reason, status)
        logger.info("source_retrying", source=source, status=status, wait=wait)
        pace.sleep(_retry_after(response) or wait)
    raise AssertionError("unreachable")  # pragma: no cover


def _retry_after(response: httpx.Response) -> float | None:
    """Seconds the server asked for, when it asked in seconds."""
    try:
        return max(0.0, float(response.headers.get("retry-after", "")))
    except ValueError:
        return None
