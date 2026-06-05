"""FastAPI application entry point for the gateway microservice."""

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler  # type: ignore[import-untyped]
from slowapi.errors import RateLimitExceeded  # type: ignore[import-untyped]

from src.infrastructure.limiter import limiter
from src.infrastructure.router import router

app = FastAPI(title="Corvus Gateway", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
