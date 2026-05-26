"""LangGraph node: generate final review and scores (stub)."""

import structlog

from ..state import AnalysisState

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def generate_review(state: AnalysisState) -> AnalysisState:
    """Generate review with scores and recommendation — stub."""
    logger.info("generate_review_stub_called", evaluation_id=state["evaluation_id"])
    return state
