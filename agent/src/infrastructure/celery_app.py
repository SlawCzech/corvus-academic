"""Celery application instance for the agent service."""

from celery import Celery

from src.infrastructure.settings import settings

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
