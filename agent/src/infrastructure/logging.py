"""Structlog configuration for the agent service.

Called from both ``main.py`` (the HTTP process) and ``celery_app.py`` (the
worker) — the two run as separate OS processes, and each needs its own root
logger wired. Calling it twice within the same process (the HTTP process
imports ``celery_app`` too, to call ``send_task``) is harmless: the handler
list is assigned, not appended.
"""

import logging
import sys

import structlog
import structlog.stdlib


def configure_logging(level: int = logging.INFO) -> None:
    """Wire structlog's rendering onto the stdlib root logger.

    Without this, every INFO event this service logs — ``run_action.started``,
    ``propose_topic_complete``, ``guidelines_retrieved`` — was silently
    dropped in the HTTP process, exactly like `app`'s identical bug. The
    worker's own logs only ever appeared because ``celery worker
    --loglevel=info`` happens to reconfigure root logging as a side effect of
    starting up; drop that flag and the worker goes just as silent. Calling
    this explicitly means the logging works because of this file, not
    because of an unrelated CLI flag someone could one day change.
    """
    root = logging.getLogger()
    root.handlers = [logging.StreamHandler(sys.stdout)]
    root.setLevel(level)

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,  # type: ignore[arg-type]  # structlog stubs defect
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )
