"""FastAPI application entry point for the agent service.

The agent service runs two processes in docker-compose:
  - HTTP server (this file): exposes /analysis endpoints
  - Celery worker: processes analysis tasks asynchronously

Both share the same codebase and Docker image.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Response, status
from kombu.exceptions import KombuError

from src.infrastructure.api.router import router
from src.infrastructure.logging import configure_logging
from src.infrastructure.worker_health import count_workers

configure_logging()

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield


app = FastAPI(title="Corvus Agent", version="0.1.0", lifespan=lifespan)

app.include_router(router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/worker")
async def health_worker(response: Response) -> dict[str, object]:
    """503 when nothing would pick up a queued action.

    Not what the containers' healthcheck asks: a worker that is briefly gone
    must not restart the API or fail a deploy.
    """
    try:
        workers = await count_workers()
    except (TimeoutError, OSError, KombuError) as exc:
        logger.warning("worker_ping_failed", error=type(exc).__name__)
        workers = 0

    if workers == 0:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", "workers": 0}
    return {"status": "ok", "workers": workers}
