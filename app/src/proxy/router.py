"""Transitional reverse proxy from `app` to the `agent` service.

Everything identity-related is now served in-process by
``src.identity.infrastructure.router`` — only `/analysis/*` still crosses a
network boundary, because analysis runs asynchronously in `agent`.

This module is TRANSITIONAL: it preserves the pre-consolidation
`/analysis/*` contract so the existing frontend flow keeps working. It is
replaced in Phase 3 by the mentoring action endpoints
(`/students/{id}/actions`), at which point this file is deleted.
"""

import httpx
import structlog
from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse

from src.shared.settings import settings

_REQUEST_ID_HEADER = "x-request-id"

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter()


# ---------- proxy helper ----------


async def _proxy(request: Request, base_url: str, path: str) -> Response:
    """Forward a request to a downstream service and stream the response back.

    Forwards body, headers (including Authorization and Cookie), and query params.
    """
    request_id: str = getattr(request.state, "request_id", "")
    bound_logger: structlog.stdlib.BoundLogger = logger.bind(
        request_id=request_id, path=path
    )

    body = await request.body()
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length", "transfer-encoding")
    }
    headers[_REQUEST_ID_HEADER] = request_id

    client: httpx.AsyncClient = request.app.state.http_client

    try:
        resp = await client.request(
            method=request.method,
            url=f"{base_url}{path}",
            content=body,
            headers=headers,
            params=dict(request.query_params),
        )
    except httpx.ConnectError as exc:
        service = base_url.split("//")[-1]
        bound_logger.error("proxy_connect_error", service=service, error=str(exc))
        return JSONResponse(
            {"detail": f"Service unavailable: {service}"},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except httpx.TimeoutException:
        bound_logger.error("proxy_timeout", base_url=base_url)
        return JSONResponse(
            {"detail": "Upstream service timed out"},
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        )

    response_headers = {
        k: v
        for k, v in resp.headers.items()
        if k.lower() not in ("content-encoding", "transfer-encoding", "content-length")
    }
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=response_headers,
        media_type=resp.headers.get("content-type"),
    )


# ---------- agent routes ----------


@router.api_route(
    "/analysis/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
async def proxy_agent_analysis(path: str, request: Request) -> Response:
    return await _proxy(request, settings.agent_url, f"/analysis/{path}")


@router.api_route(
    "/analysis",
    methods=["GET", "POST"],
)
async def proxy_agent_analysis_root(request: Request) -> Response:
    return await _proxy(request, settings.agent_url, "/analysis")
