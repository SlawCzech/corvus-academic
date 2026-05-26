"""LangGraph node: check conformance with university guidelines (stub)."""

import structlog

from ..state import AnalysisState

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def check_requirements(state: AnalysisState) -> AnalysisState:
    """Check conformance with university requirements — stub."""
    logger.info("check_requirements_stub_called", evaluation_id=state["evaluation_id"])
    return state
