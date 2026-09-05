"""FastAPI application entry point for the consolidated `app` service.

`app` merges what used to be three separate services:
  - identity  — auth, users, roles/permissions, audit log, API-key vault
  - parser    — PDF/DOCX text extraction (now an in-process module)
  - gateway   — reverse proxy (only the `/analysis/*` → agent hop survives)

plus `mentoring`, the bounded context the pivot is built on: students,
meeting notes, and (from Phase 2) the AI action log.

`agent` remains a separate service: LLM work is slow and asynchronous.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.document.router import router as document_router
from src.identity.infrastructure.router import router as identity_router
from src.mentoring.infrastructure.router import router as mentoring_router
from src.proxy.health import health_router
from src.proxy.router import router as proxy_router
from src.shared.logging import configure_logging
from src.shared.middleware import request_id_middleware
from src.shared.settings import settings

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Hold one shared HTTP client for the lifetime of the process."""
    app.state.http_client = httpx.AsyncClient(timeout=30.0)
    yield
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
app.include_router(document_router)
app.include_router(proxy_router)
app.include_router(health_router)
