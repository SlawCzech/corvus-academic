"""Health check endpoint for the gateway service."""

import httpx
from fastapi import APIRouter, Request

from src.infrastructure.settings import settings

health_router = APIRouter()


@health_router.get("/health")
async def health(request: Request) -> dict[str, object]:
    client: httpx.AsyncClient = request.app.state.http_client
    services: dict[str, str] = {}

    for name, url in [("identity", settings.identity_url), ("agent", settings.agent_url)]:
        try:
            resp = await client.get(f"{url}/health", timeout=3.0)
            services[name] = "ok" if resp.status_code == 200 else "degraded"
        except httpx.ConnectError:
            services[name] = "unavailable"
        except httpx.TimeoutException:
            services[name] = "timeout"

    overall = "ok" if all(v == "ok" for v in services.values()) else "degraded"
    return {"status": overall, "services": services}
