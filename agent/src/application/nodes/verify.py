"""LangGraph node: check the findings against the thesis before anyone reads them.

Runs after the analyses and before the review — the join where every
finding is finally in one place. No model: see `grounding.py` for what is
checked and why it is plain string work.

It replaces the findings list rather than adding to it. `findings` sums what
each branch returns (`operator.add`), which is right for three branches
writing at once and wrong for a node whose whole job is to take findings
away; `Overwrite` bypasses the reducer for this one write.
"""

import structlog
from langgraph.types import Overwrite

from src.application.grounding import verify_findings

from ..state import ActionState, VerifyUpdate

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def verify(state: ActionState) -> VerifyUpdate:
    """Drop ungrounded findings and merge duplicates across analyses."""
    try:
        result = verify_findings(
            state["findings"], str(state["context"].get("text", ""))
        )
    except Exception as exc:
        # A check that breaks must not cost the review its findings: pass
        # them through unchecked and say so.
        logger.error("verify_findings_failed", error=str(exc))
        return {"node_errors": [f"verify: {exc}"]}

    logger.info(
        "findings_verified",
        kept=len(result.kept),
        ungrounded=len(result.ungrounded),
        merged=len(result.merged),
    )
    return {
        "findings": Overwrite(result.kept),
        "verification": result.summary(),
    }
