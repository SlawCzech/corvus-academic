"""LangGraph node: propose thesis topics for one student.

The first action of the mentoring platform, and the simplest: it needs no
uploaded document and no guidelines file — a student record and whatever the
supervisor typed is enough.
"""

from collections.abc import Sequence
from typing import Any

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from src.application.prompts import propose_topic as prompts
from src.application.replies import TOPIC_PROPOSAL
from src.application.structured import invoke_structured
from src.infrastructure.llm_factory import get_llm
from src.infrastructure.provider_errors import raise_if_provider_error

from ..state import ActionState

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _user_message(ctx: dict[str, Any]) -> str:
    """Render the assembled context as the prompt's user turn."""
    lines = [
        f"Field of study: {ctx.get('field_of_study') or 'unspecified'}",
        f"Thesis type: {ctx.get('thesis_type') or 'bachelor'}",
    ]
    if ctx.get("current_topic"):
        lines.append(
            f"Current working topic (propose alternatives or refinements): "
            f"{ctx['current_topic']}"
        )
    if ctx.get("detail"):
        lines.append(f"Supervisor's instructions: {ctx['detail']}")
    notes: Sequence[str] = ctx.get("recent_notes") or []
    if notes:
        joined = "\n".join(f"- {n}" for n in notes)
        lines.append(f"Recent meeting notes:\n{joined}")
    return "\n\n".join(lines)


def propose_topic(state: ActionState) -> ActionState:
    """Propose three thesis topics and put them in the action's output."""
    try:
        ctx = state["context"]
        llm = get_llm(state["model"])
        reply = invoke_structured(
            llm,
            [
                SystemMessage(  # type: ignore[attr-defined]
                    content=prompts.get_system_prompt(state.get("language", "pl"))
                ),
                HumanMessage(content=_user_message(ctx)),
            ],
            TOPIC_PROPOSAL,
            node="propose_topic",
        )
        topics = [t.model_dump() for t in reply.topics]
        recommended = reply.recommended if 0 <= reply.recommended < len(topics) else 0

        logger.info(
            "propose_topic_complete",
            action_id=state["action_id"],
            topic_count=len(topics),
        )
        result: ActionState = state.copy()
        result["output"] = {"topics": topics, "recommended": recommended}
        result["status"] = "proposed"
        result["error"] = None
        return result
    except Exception as exc:
        # Same contract as every other node: record the error and let the
        # graph finish so the task can persist a failure the promoter can
        # actually see. The one exception is the provider's account — no
        # credits, a refused key — which ends the run: see `provider_errors`.
        raise_if_provider_error(exc)
        logger.error("propose_topic_failed", error=str(exc))
        result = state.copy()
        result["error"] = str(exc)
        return result
