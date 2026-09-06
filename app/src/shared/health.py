"""Health check endpoint for the `app` service.

Identity is now in-process, so the only downstream dependency worth probing
over the network is `agent`.
"""

import httpx
from fastapi import APIRouter, Request

from src.shared.settings import settings

health_router = APIRouter()


@health_router.get("/health")
async def health(request: Request) -> dict[str, object]:
    client: httpx.AsyncClient = request.app.state.http_client
    services: dict[str, str] = {}

    try:
        resp = await client.get(f"{settings.agent_url}/health", timeout=3.0)
        services["agent"] = "ok" if resp.status_code == 200 else "degraded"
    except httpx.ConnectError:
        services["agent"] = "unavailable"
    except httpx.TimeoutException:
        services["agent"] = "timeout"

    overall = "ok" if all(v == "ok" for v in services.values()) else "degraded"
    return {"status": overall, "services": services}
