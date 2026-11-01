"""Health check endpoint for the `app` service.

Identity is now in-process, so the only downstream dependency worth probing
over the network is `agent` — and, through it, the Celery worker, since a dead
worker leaves actions in `pending` with nothing else showing it.
"""

import asyncio

import httpx
from fastapi import APIRouter, Request

from src.shared.settings import settings

health_router = APIRouter()


async def _probe(client: httpx.AsyncClient, url: str) -> str:
    try:
        resp = await client.get(url, timeout=3.0)
    except httpx.ConnectError:
        return "unavailable"
    except httpx.TimeoutException:
        return "timeout"
    if resp.status_code == 503:
        return "unavailable"
    return "ok" if resp.status_code == 200 else "degraded"


@health_router.get("/health")
async def health(request: Request) -> dict[str, object]:
    """Always 200, `degraded` included.

    `deploy.sh` and the container healthchecks read only the status code, so
    anything else here would roll a deploy back over a worker that is
    restarting. The body is for people and monitors.
    """
    client: httpx.AsyncClient = request.app.state.http_client

    # Side by side: one after the other, two 3 s timeouts would outlast the
    # containers' 5 s healthcheck.
    agent, worker = await asyncio.gather(
        _probe(client, f"{settings.agent_url}/health"),
        _probe(client, f"{settings.agent_url}/health/worker"),
    )
    services = {"agent": agent, "worker": worker}

    overall = "ok" if all(v == "ok" for v in services.values()) else "degraded"
    return {"status": overall, "services": services}
