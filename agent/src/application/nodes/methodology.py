"""LangGraph node: analyze thesis methodology and bibliography (stub)."""

import structlog

from ..state import AnalysisState

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def analyze_methodology(state: AnalysisState) -> AnalysisState:
    """Analyze methodology and bibliography sections — stub, returns state unchanged."""
    logger.info("analyze_methodology_stub_called", evaluation_id=state["evaluation_id"])
    return state
