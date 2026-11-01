"""Is any Celery worker answering? The check behind `GET /health/worker`.

`inspect().ping()` is blocking and always takes its whole timeout, because it
collects replies until then. Left alone it is also worse than slow: on the
app's connection pool a silent Redis holds it forever and thirty at once never
return. `/health` is public through the site, so all of this has to hold with
anyone calling it: each ping gets its own connection with socket timeouts, runs
in a thread, and concurrent callers share one ping.
"""

import asyncio

from src.infrastructure.celery_app import celery_app

_PING_TIMEOUT_SECONDS = 1.0
# How long a caller waits. Above the ping's own second, below the 3 s `app`
# gives this endpoint. A dead broker keeps the thread for ~6 s of kombu's
# retries, and the caller should not have to sit through them.
_DEADLINE_SECONDS = 2.0
_BROKER_OPTIONS = {"socket_timeout": 2.0, "socket_connect_timeout": 1.0}

_in_flight: asyncio.Future[int] | None = None


def _ping() -> int:
    with celery_app.connection_for_read(transport_options=_BROKER_OPTIONS) as conn:
        replies = celery_app.control.inspect(
            timeout=_PING_TIMEOUT_SECONDS, connection=conn
        ).ping()
    return len(replies or {})


async def count_workers() -> int:
    """How many workers replied. Raises if the broker could not be asked.

    Shielded, so a caller's deadline leaves the shared ping running: the thread
    could not be cancelled anyway, and the next caller must join it rather than
    start another one beside it.
    """
    global _in_flight
    if _in_flight is None or _in_flight.done():
        _in_flight = asyncio.ensure_future(asyncio.to_thread(_ping))
    return await asyncio.wait_for(asyncio.shield(_in_flight), _DEADLINE_SECONDS)
