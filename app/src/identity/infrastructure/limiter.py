"""Rate limits for the endpoints that take a password or open a request.

In-process, per client and per endpoint: one `app` process serves the site,
and a restart forgetting the counts costs nothing.

It replaces fastapi-limiter, which got both wrong: its in-memory backend kept
one bucket for every key, so five logins a minute were shared by the whole
world, and since FastAPI 0.162 its route lookup ended every limited request
in a 500.
"""

import time
from collections import deque
from collections.abc import Callable

from fastapi import HTTPException, Request, status


def _client(request: Request) -> str:
    """The browser's address: Caddy's ``X-Forwarded-For``, else the peer.

    Requests reach `app` from the frontend's server; the routes behind a
    limit pass the header on (`forwardedFor` in `lib/appProxy.ts`), and in
    production Caddy sets it, replacing whatever the browser sent.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimit:
    """At most ``limit`` requests per ``window_seconds``, per client and path.

    A FastAPI dependency: refused requests get a 429 before the endpoint
    runs. A sliding window — the timestamps of the last ``limit`` requests —
    so a burst at the edge of a minute is not let through twice.
    """

    def __init__(
        self,
        limit: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}

    async def __call__(self, request: Request) -> None:
        now = self._clock()
        self._forget_idle(now)
        key = f"{_client(request)}:{request.method}:{request.url.path}"
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] >= self._window:
            hits.popleft()
        if len(hits) >= self._limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too Many Requests",
            )
        hits.append(now)

    def _forget_idle(self, now: float) -> None:
        """Drop clients whose last request is out of the window."""
        idle = [
            k for k, h in self._hits.items() if not h or now - h[-1] >= self._window
        ]
        for key in idle:
            del self._hits[key]


login_rate_limit = RateLimit(limit=5, window_seconds=60)
access_request_rate_limit = RateLimit(limit=3, window_seconds=60)
