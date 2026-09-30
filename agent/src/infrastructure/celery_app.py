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
    # Acknowledge a task when it finishes, not when a worker takes it, and
    # hand it back if the worker process dies mid-run. With graph checkpoints
    # the redelivered task resumes where the dead one stopped, so a killed
    # worker costs one step of a review, not the review.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Redis redelivers an unacknowledged task after this long, running or
    # not. Well above the longest review (~15 min on a local model) so a slow
    # run is never started twice; a dead worker's task comes back within it.
    broker_transport_options={"visibility_timeout": 2 * 60 * 60},
)
