"""FastAPI application entry point for the consolidated `app` service.

`app` merges what used to be three separate services:
  - identity  — auth, users, roles/permissions, audit log, API-key vault
  - parser    — PDF/DOCX text extraction (now an in-process module, called
                when a thesis version is uploaded)
  - gateway   — reverse proxy (gone: `app` calls `agent` explicitly now)

plus `mentoring`, the bounded context the pivot is built on: students,
meeting notes, thesis versions and the AI action log.

`agent` remains a separate service: LLM work is slow and asynchronous.
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.identity.infrastructure.router import router as identity_router
from src.mentoring.infrastructure.retention import run_retention_sweeps
from src.mentoring.infrastructure.router import router as mentoring_router
from src.shared.health import health_router
from src.shared.logging import configure_logging
from src.shared.middleware import request_id_middleware
from src.shared.settings import settings

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Hold one shared HTTP client, and run the retention sweep, for the
    lifetime of the process."""
    app.state.http_client = httpx.AsyncClient(timeout=30.0)
    sweeps = (
        asyncio.create_task(
            run_retention_sweeps(settings.retention_sweep_interval_hours)
        )
        if settings.retention_sweep_interval_hours > 0
        else None
    )
    yield
    if sweeps is not None:
        sweeps.cancel()
    await app.state.http_client.aclose()


app = FastAPI(title="Corvus App", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,  # type: ignore[arg-type]  # starlette stubs defect
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(request_id_middleware)

app.include_router(identity_router)
app.include_router(mentoring_router)
app.include_router(health_router)
