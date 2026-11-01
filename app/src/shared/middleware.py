"""HTTP middleware for the `app` service."""

import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def request_id_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Give every request an id, and echo it back on the response."""
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response


async def access_log_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Log every request but the healthchecks': method, path, status, time.

    The path goes without its query string, and nothing from headers or
    bodies. The time runs to the first byte, so it undercounts a long download.
    """
    path = request.url.path
    if path == "/health":
        return await call_next(request)

    started = time.perf_counter()
    status_code = 500  # what the client gets when the handler raises
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        logger.info(
            "http_request",
            method=request.method,
            path=path,
            status=status_code,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )
