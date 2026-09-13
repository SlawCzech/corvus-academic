"""Celery application instance for the agent service."""

from celery import Celery

from src.infrastructure.logging import configure_logging
from src.infrastructure.settings import settings

# The worker process never imports main.py, so nothing else wires this up —
# without this call the worker's structured logs exist only because
# `--loglevel=info` happens to reconfigure root logging as a side effect.
configure_logging()

celery_app = Celery(
    "agent",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.application.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
