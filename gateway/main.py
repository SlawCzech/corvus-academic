"""FastAPI application entry point for the gateway microservice."""

from fastapi import FastAPI

from src.infrastructure.router import router

app = FastAPI(title="Corvus Gateway", version="0.1.0")
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
