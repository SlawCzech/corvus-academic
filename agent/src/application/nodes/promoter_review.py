"""LangGraph node: the promoter decides which findings the review may use.

Runs between `verify` and the review. When the promoter asked to see the
findings first, the node calls `interrupt`: the run stops, its state stays in
the checkpoint, and the task reports ``awaiting_input`` with the findings in
its result. The promoter unticks the ones they disagree with; `app` resumes
the run with ``Command(resume={"accepted": [indices]})``, and this node — run
again from the top, as a resumed node always is — gets that decision back as
the return value of `interrupt` and keeps only those findings.

When they did not ask, the node is a pass-through. It is always in the graph,
so the graph a run resumes into is the graph it was paused in.
"""

from typing import Any, cast

import structlog
from langgraph.types import Overwrite, interrupt

from ..state import ActionState, VerifyUpdate

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Context flag, set by `app` from the action panel's checkbox.
PROMOTER_REVIEWS_FINDINGS = "promoter_reviews_findings"


def promoter_review(state: ActionState) -> VerifyUpdate:
    """Pause for the promoter's choice of findings, if they asked to choose."""
    if not state["context"].get(PROMOTER_REVIEWS_FINDINGS):
        return {}

    findings = state["findings"]
    decision: Any = interrupt({"finding_count": len(findings)})

    raw = (
        cast(dict[str, Any], decision).get("accepted")
        if isinstance(decision, dict)
        else None
    )
    if not isinstance(raw, list):
        # A resume without a usable decision keeps everything: losing
        # findings the promoter never saw rejected is worse than a longer
        # review.
        logger.warning("promoter_review_without_decision")
        return {}
    accepted = {i for i in cast(list[Any], raw) if isinstance(i, int)}
    kept = [f for i, f in enumerate(findings) if i in accepted]
    logger.info(
        "promoter_reviewed_findings", kept=len(kept), rejected=len(findings) - len(kept)
    )
    return {"findings": Overwrite(kept)}
