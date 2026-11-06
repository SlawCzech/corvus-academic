"""LangGraph node: draft a rubric from a university's regulation.

The one action with no student: `app` sends the regulation's text, the kind
of thesis and, when the catalog has one, a published rubric as a model of
the shape. The output is a draft an administrator checks against the
original and publishes — never a rubric anything is judged by until then
(ADR 0025). Only the regulation is sent; no thesis is involved.
"""

from typing import Any

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from src.application.prompts import draft_rubric as prompts
from src.application.replies import RUBRIC_DRAFT
from src.application.structured import invoke_structured
from src.infrastructure.llm_factory import get_llm
from src.infrastructure.provider_errors import raise_if_provider_error

from ..state import ActionState

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _user_message(ctx: dict[str, Any]) -> str:
    thesis_type = str(ctx.get("thesis_type", ""))
    kind = prompts.THESIS_TYPES.get(thesis_type, thesis_type)
    lines = [f"Draft the rubric for {kind}."]
    if ctx.get("university"):
        lines.append(f"University: {ctx['university']}")
    if ctx.get("set_name"):
        lines.append(f"The set of rules is called: {ctx['set_name']}")
    if ctx.get("regulation_filename"):
        lines.append(f"The regulation's file: {ctx['regulation_filename']}")
    lines.append(f"<regulation>\n{ctx.get('regulation', '')}\n</regulation>")
    return "\n\n".join(lines)


def draft_rubric(state: ActionState) -> ActionState:
    """Read the regulation and return the four sections and the thresholds."""
    try:
        ctx = state["context"]
        if not str(ctx.get("regulation", "")).strip():
            raise ValueError("the regulation has no text to read")

        reply = invoke_structured(
            get_llm(),
            [
                SystemMessage(  # type: ignore[attr-defined]
                    content=prompts.get_system_prompt(ctx.get("example_rubric"))
                ),
                HumanMessage(content=_user_message(ctx)),
            ],
            RUBRIC_DRAFT,
            node="draft_rubric",
        )

        logger.info(
            "draft_rubric_complete",
            action_id=state["action_id"],
            doubts=len(reply.doubts),
        )
        result: ActionState = state.copy()
        result["output"] = reply.model_dump()
        result["status"] = "drafted"
        result["error"] = None
        return result
    except Exception as exc:
        raise_if_provider_error(exc)
        logger.error("draft_rubric_failed", error=str(exc))
        result = state.copy()
        result["error"] = str(exc)
        return result
