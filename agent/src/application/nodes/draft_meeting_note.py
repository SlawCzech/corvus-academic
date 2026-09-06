"""LangGraph node: turn a supervisor's rough points into a meeting note.

The one action whose accepted output becomes a human-authored record: `app`
stores it as a MeetingNote carrying `source_action_id`, so a note drafted
here is always distinguishable from one the promoter typed.
"""

from collections.abc import Sequence
from typing import Any

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from src.application.json_output import as_list, parse_json_object
from src.application.prompts import draft_meeting_note as prompts
from src.infrastructure.llm_factory import get_llm

from ..state import ActionState

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _user_message(ctx: dict[str, Any]) -> str:
    lines = [f"Rough notes from the meeting:\n{ctx.get('detail', '')}"]
    if ctx.get("current_topic"):
        lines.append(f"Thesis topic: {ctx['current_topic']}")
    notes: Sequence[str] = ctx.get("recent_notes") or []
    if notes:
        joined = "\n".join(f"- {n}" for n in notes)
        lines.append(f"Earlier meeting notes, for continuity:\n{joined}")
    return "\n\n".join(lines)


def draft_meeting_note(state: ActionState) -> ActionState:
    """Draft the note the promoter will review, edit and accept."""
    try:
        ctx = state["context"]
        if not str(ctx.get("detail", "")).strip():
            raise ValueError("no rough notes to write up")

        llm = get_llm(state["model"])
        response = llm.invoke(
            [
                SystemMessage(  # type: ignore[attr-defined]
                    content=prompts.get_system_prompt(state.get("language", "pl"))
                ),
                HumanMessage(content=_user_message(ctx)),
            ]
        )
        data = parse_json_object(response.content)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]

        content = str(data.get("content", "")).strip()
        if not content:
            raise ValueError("model returned an empty note")

        logger.info("draft_meeting_note_complete", action_id=state["action_id"])
        result: ActionState = state.copy()
        result["output"] = {
            "content": content,
            "topics_discussed": [
                str(t) for t in as_list(data.get("topics_discussed"))
            ],
            "agreed_actions": [
                str(a) for a in as_list(data.get("agreed_actions"))
            ],
        }
        result["status"] = "drafted"
        result["error"] = None
        return result
    except Exception as exc:
        logger.error("draft_meeting_note_failed", error=str(exc))
        result = state.copy()
        result["error"] = str(exc)
        return result
