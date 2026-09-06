"""HTTP middleware for the `app` service."""

import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response


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
