"""LangGraph node: propose thesis topics for one student.

The first action of the mentoring platform, and the simplest: it needs no
uploaded document and no guidelines file — a student record and whatever the
supervisor typed is enough.
"""

import json
import re
from collections.abc import Sequence
from typing import Any

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from src.application.prompts import propose_topic as prompts
from src.infrastructure.llm_factory import get_llm

from ..state import ActionState

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _extract_json(text: str) -> str:
    """Strip a markdown code fence if the model wrapped its JSON in one."""
    match = _FENCE_RE.search(text)
    return match.group(1) if match else text.strip()


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
        response = llm.invoke(
            [
                SystemMessage(  # type: ignore[attr-defined]
                    content=prompts.get_system_prompt(state.get("language", "pl"))
                ),
                HumanMessage(content=_user_message(ctx)),
            ]
        )
        raw: str | Sequence[object] = response.content  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        content: str = raw if isinstance(raw, str) else json.dumps(raw)
        data: dict[str, Any] = json.loads(_extract_json(content))

        topics: list[dict[str, Any]] = list(data.get("topics") or [])
        if not topics:
            raise ValueError("model returned no topics")

        recommended = data.get("recommended", 0)
        if not isinstance(recommended, int) or not 0 <= recommended < len(topics):
            recommended = 0

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
        # Same contract as every other node: never raise, record the error and
        # let the graph finish so the task can persist a failure the promoter
        # can actually see.
        logger.error("propose_topic_failed", error=str(exc))
        result = state.copy()
        result["error"] = str(exc)
        return result
