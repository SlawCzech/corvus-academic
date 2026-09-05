"""HTTP middleware for the gateway service."""

import uuid

from fastapi import Request, Response


async def request_id_middleware(request: Request, call_next: object) -> Response:
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    request.state.request_id = request_id
    response: Response = await call_next(request)  # type: ignore[operator]
    response.headers["x-request-id"] = request_id
    return response
