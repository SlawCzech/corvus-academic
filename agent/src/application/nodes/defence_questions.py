"""LangGraph node: prepare defence questions from the thesis.

The one action aimed at the defence itself rather than at improving the
draft: what a committee member would ask, and what the answer would show.
"""

from typing import Any

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from src.application.excerpt import render_document_block
from src.application.prompts import defence_questions as prompts
from src.application.replies import DEFENCE_QUESTIONS
from src.application.structured import invoke_structured
from src.infrastructure.llm_factory import get_llm

from ..state import ActionState

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# The committee reads the whole work, but the model gets a slice — enough for
# it to ask about the argument rather than about the appendices. The map that
# travels with the slice names the chapters it does not reach, so a question
# can still be aimed at the results or the conclusions.
_MAX_TEXT_CHARS = 14000
_EXPECTED_QUESTIONS = 3


def _user_message(ctx: dict[str, Any]) -> str:
    lines = [
        f"Thesis topic: {ctx.get('current_topic') or 'not settled yet'}",
        f"Field of study: {ctx.get('field_of_study') or 'unspecified'}",
        f"Thesis type: {ctx.get('thesis_type') or 'bachelor'}",
    ]
    if ctx.get("detail"):
        lines.append(f"Supervisor's instructions: {ctx['detail']}")
    lines.append(render_document_block(ctx, head_chars=_MAX_TEXT_CHARS))
    return "\n\n".join(lines)


def defence_questions(state: ActionState) -> ActionState:
    """Produce three defence questions and put them in the action's output."""
    try:
        ctx = state["context"]
        if not str(ctx.get("text", "")).strip():
            raise ValueError("no thesis text to ask questions about")

        llm = get_llm(state["model"])
        reply = invoke_structured(
            llm,
            [
                SystemMessage(  # type: ignore[attr-defined]
                    content=prompts.get_system_prompt(state.get("language", "pl"))
                ),
                HumanMessage(content=_user_message(ctx)),
            ],
            DEFENCE_QUESTIONS,
            node="defence_questions",
        )
        questions = [q.model_dump() for q in reply.questions]

        logger.info(
            "defence_questions_complete",
            action_id=state["action_id"],
            question_count=len(questions),
            expected=_EXPECTED_QUESTIONS,
        )
        result: ActionState = state.copy()
        result["output"] = {"questions": questions}
        result["status"] = "questions_ready"
        result["error"] = None
        return result
    except Exception as exc:
        logger.error("defence_questions_failed", error=str(exc))
        result = state.copy()
        result["error"] = str(exc)
        return result
