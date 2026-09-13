"""Structlog configuration for the app service."""

import logging
import sys

import structlog
import structlog.stdlib


def configure_logging(level: int = logging.INFO) -> None:
    """Wire structlog's rendering onto the stdlib root logger.

    ``structlog.configure`` alone only shapes how one call renders; it is
    stdlib ``logging`` that decides whether the rendered line reaches
    anywhere at all. Without a handler on the root logger — the state this
    function used to leave things in — every INFO event (``student_created``,
    ``action_dispatched``, ``draft_uploaded``, the entire success path) was
    silently dropped, and ERROR/WARNING only survived by accident, through
    Python's own ``logging.lastResort`` fallback catching them on their way
    out. Assigning a handler here, rather than appending one, keeps this
    idempotent if the app or a test imports this twice.
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
