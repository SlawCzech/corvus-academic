"""Structlog configuration for the gateway service."""

import structlog
import structlog.stdlib


def configure_logging() -> None:
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
