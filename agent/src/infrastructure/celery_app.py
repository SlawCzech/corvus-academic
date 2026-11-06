"""Celery application instance for the agent service."""

from celery import Celery

from src.infrastructure.logging import configure_logging
from src.infrastructure.settings import settings

# The worker process never imports main.py, so nothing else wires this up —
# without this call the worker's structured logs exist only because
# `--loglevel=info` happens to reconfigure root logging as a side effect.
configure_logging()

TASK_SOFT_TIME_LIMIT_SECONDS = 30 * 60
VISIBILITY_TIMEOUT_SECONDS = 45 * 60

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
    # No run gets longer than this. The longest real one (a review, a long
    # bibliography) takes a few minutes; a run still going after half an
    # hour is stuck on something, and holds one of the worker's few slots.
    # The soft limit raises inside the task, which records the failure
    # (`tasks._fail_or_retry`); the hard one kills a run that ignored it.
    task_soft_time_limit=TASK_SOFT_TIME_LIMIT_SECONDS,
    task_time_limit=TASK_SOFT_TIME_LIMIT_SECONDS + 5 * 60,
    # Redis redelivers an unacknowledged task after this long, running or
    # not — so above the hard limit, or a live run would be started twice.
    # A dead worker's task comes back within it.
    broker_transport_options={"visibility_timeout": VISIBILITY_TIMEOUT_SECONDS},
    # On a cold shutdown (SIGTERM is remapped to it in both composes), running
    # tasks get this long to finish before they are handed back to the queue.
    worker_soft_shutdown_timeout=30.0,
)
