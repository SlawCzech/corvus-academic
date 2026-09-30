"""LangGraph node: compare two draft versions and judge the progress."""

from typing import Any

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from src.application.prompts import check_progress as prompts
from src.application.replies import PROGRESS
from src.application.structured import invoke_structured
from src.infrastructure.llm_factory import get_llm
from src.infrastructure.provider_errors import raise_if_provider_error

from ..state import ActionState

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Half the budget per version, so both fit next to each other.
_MAX_TEXT_CHARS = 7000


def _slice(text: str) -> str:
    return (
        text[:_MAX_TEXT_CHARS] + "\n\n[...text truncated...]"
        if len(text) > _MAX_TEXT_CHARS
        else text
    )


def _user_message(ctx: dict[str, Any]) -> str:
    previous = str(ctx.get("previous_text", ""))
    current = str(ctx.get("current_text", ""))
    lines = [
        f"Thesis topic: {ctx.get('current_topic') or 'not settled yet'}",
        f"Previous version (v{ctx.get('previous_version', '?')}):\n{_slice(previous)}",
        f"Current version (v{ctx.get('current_version', '?')}):\n{_slice(current)}",
    ]
    if ctx.get("detail"):
        lines.append(f"Supervisor's instructions: {ctx['detail']}")
    return "\n\n".join(lines)


def check_progress(state: ActionState) -> ActionState:
    """Report what changed between two versions of the thesis."""
    try:
        ctx = state["context"]
        if not str(ctx.get("previous_text", "")).strip():
            raise ValueError("no earlier version to compare against")
        if not str(ctx.get("current_text", "")).strip():
            raise ValueError("no current version to compare")

        llm = get_llm(state["model"])
        reply = invoke_structured(
            llm,
            [
                SystemMessage(  # type: ignore[attr-defined]
                    content=prompts.get_system_prompt(state.get("language", "pl"))
                ),
                HumanMessage(content=_user_message(ctx)),
            ],
            PROGRESS,
            node="check_progress",
        )

        logger.info(
            "check_progress_complete",
            action_id=state["action_id"],
            change_count=len(reply.changes),
        )
        result: ActionState = state.copy()
        result["output"] = {
            "summary": reply.summary,
            "changes": [c.model_dump() for c in reply.changes],
            "concerns": reply.concerns,
            "next_steps": reply.next_steps,
        }
        result["status"] = "progress_checked"
        result["error"] = None
        return result
    except Exception as exc:
        raise_if_provider_error(exc)
        logger.error("check_progress_failed", error=str(exc))
        result = state.copy()
        result["error"] = str(exc)
        return result
