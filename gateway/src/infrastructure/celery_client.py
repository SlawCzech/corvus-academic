"""Thin Celery client for dispatching tasks to the agent worker."""

from typing import Any

import structlog
from celery import Celery

from src.infrastructure.settings import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_TASK_NAME = "src.application.tasks.analyze_thesis"


def _make_celery_app() -> Celery:
    app = Celery()
    app.conf.update(
        broker_url=settings.redis_url,
        result_backend=settings.redis_url,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
    )
    return app


celery_app = _make_celery_app()


def send_analysis_task(
    evaluation_id: str,
    text: str,
    guidelines: str,
    metadata: dict[str, str],
    model: str = "qwen3:30b-a3b",
    mode: str = "full",
) -> str:
    """Dispatch analyze_thesis to the Celery worker and return the task ID."""
    async_result = celery_app.send_task(
        _TASK_NAME,
        args=[evaluation_id, text, guidelines, metadata],
        kwargs={"model": model, "mode": mode},
    )
    task_id: str = str(async_result.id)
    logger.info(
        "analysis_task_sent",
        task_id=task_id,
        evaluation_id=evaluation_id,
        model=model,
        mode=mode,
    )
    return task_id


def get_task_result(task_id: str) -> dict[str, Any]:
    """Return the current status and result payload for a Celery task."""
    async_result = celery_app.AsyncResult(task_id)
    celery_status = async_result.status
    if celery_status == "SUCCESS":
        status = "done"
    elif celery_status in ("FAILURE", "REVOKED"):
        status = "error"
    else:
        status = "analyzing"
    result: Any = async_result.result if async_result.ready() else None
    return {"status": status, "result": result}
