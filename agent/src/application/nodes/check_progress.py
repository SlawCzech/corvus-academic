"""LangGraph node: compare two draft versions and judge the progress."""

from typing import Any, cast

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from src.application.brief import render_brief
from src.application.excerpt import reading_budget
from src.application.prompts import check_progress as prompts
from src.application.replies import PROGRESS
from src.application.structured import invoke_structured
from src.infrastructure.llm_factory import get_llm
from src.infrastructure.provider_errors import raise_if_provider_error

from ..state import ActionState

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# On the local model: half the budget per version, so both fit next to each
# other. A hosted model compares the two versions whole — what a student adds
# between versions is rarely on the first pages.
_MAX_TEXT_CHARS = 7000


def _slice(text: str) -> str:
    budget = reading_budget(_MAX_TEXT_CHARS)
    if budget is None or len(text) <= budget:
        return text
    return text[:budget] + "\n\n[...text truncated...]"


def _meeting_notes(ctx: dict[str, Any]) -> list[str]:
    """The notes with how to read them, or nothing if there were no meetings."""
    notes = cast(list[str], ctx.get("meeting_notes") or [])
    if not notes:
        return []
    joined = "\n---\n".join(notes)
    return [
        f"Meeting notes from between the two versions, oldest first:\n{joined}\n"
        f"{prompts.NOTES_RULE}"
    ]


def _user_message(ctx: dict[str, Any]) -> str:
    previous = str(ctx.get("previous_text", ""))
    current = str(ctx.get("current_text", ""))
    lines = [
        render_brief(ctx),
        *_meeting_notes(ctx),
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
