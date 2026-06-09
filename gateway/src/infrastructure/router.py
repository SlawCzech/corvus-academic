"""FastAPI router for the gateway service.

Gateway is a pure reverse proxy — no domain logic, no database.
It verifies JWT locally and forwards all requests to the appropriate service:

  /auth/*, /users/*, /admin/*, /settings/*  →  identity service
  /analysis/*                               →  agent service
"""

import structlog
from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse

import httpx

from src.infrastructure.settings import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter()


# ---------- proxy helper ----------


async def _proxy(request: Request, base_url: str, path: str) -> Response:
    """Forward a request to a downstream service and stream the response back.

    Forwards body, headers (including Authorization and Cookie), and query params.
    Cookies (e.g. httpOnly refresh_token) are passed through transparently.
    """
    body = await request.body()
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length", "transfer-encoding")
    }

    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
            resp = await client.request(
                method=request.method,
                url=path,
                content=body,
                headers=headers,
                params=dict(request.query_params),
            )
    except httpx.ConnectError as exc:
        service = base_url.split("//")[-1]
        logger.error("proxy_connect_error", service=service, path=path, error=str(exc))
        return JSONResponse(
            {"detail": f"Service unavailable: {service}"},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except httpx.TimeoutException:
        logger.error("proxy_timeout", base_url=base_url, path=path)
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


# ---------- identity routes ----------


@router.api_route(
    "/auth/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
async def proxy_identity_auth(path: str, request: Request) -> Response:
    return await _proxy(request, settings.identity_url, f"/auth/{path}")


@router.api_route(
    "/users/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
async def proxy_identity_users(path: str, request: Request) -> Response:
    return await _proxy(request, settings.identity_url, f"/users/{path}")


@router.api_route(
    "/users",
    methods=["GET", "POST"],
)
async def proxy_identity_users_root(request: Request) -> Response:
    return await _proxy(request, settings.identity_url, "/users")


@router.api_route(
    "/admin/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
async def proxy_identity_admin(path: str, request: Request) -> Response:
    return await _proxy(request, settings.identity_url, f"/admin/{path}")


@router.api_route(
    "/settings/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
async def proxy_identity_settings(path: str, request: Request) -> Response:
    return await _proxy(request, settings.identity_url, f"/settings/{path}")


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
