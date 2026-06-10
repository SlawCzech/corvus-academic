"""FastAPI application entry point for the gateway microservice.

Gateway is a pure reverse proxy — no database, no JWT logic, no domain.
All requests are forwarded to identity or agent service.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.infrastructure.health import health_router
from src.infrastructure.logging import configure_logging
from src.infrastructure.middleware import request_id_middleware
from src.infrastructure.router import router
from src.infrastructure.settings import settings

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    app.state.http_client = httpx.AsyncClient(timeout=30.0)
    yield
    await app.state.http_client.aclose()


app = FastAPI(title="Corvus Gateway", version="0.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,  # type: ignore[arg-type]  # starlette stubs defect
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(request_id_middleware)

app.include_router(router)
app.include_router(health_router)
