"""FastAPI application entry point for the agent service.

The agent service runs two processes in docker-compose:
  - HTTP server (this file): exposes /analysis endpoints
  - Celery worker: processes analysis tasks asynchronously

Both share the same codebase and Docker image.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
import structlog.stdlib
from fastapi import FastAPI

from src.infrastructure.api.router import router

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield


app = FastAPI(title="Corvus Agent", version="0.1.0", lifespan=lifespan)

app.include_router(router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
