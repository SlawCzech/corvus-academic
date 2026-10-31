"""LangGraph node: summarise a fragment and say if it is going the right way."""

from typing import Any, cast

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from src.application.excerpt import reading_budget
from src.application.grounding import ThesisText
from src.application.prompts import review_fragment as prompts
from src.application.replies import FRAGMENT_REVIEW, FragmentChangeReply
from src.application.structured import invoke_structured
from src.infrastructure.llm_factory import get_llm
from src.infrastructure.provider_errors import raise_if_provider_error

from ..state import ActionState

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# On the local model; a hosted model reads everything. A later round shares
# this between the two texts, as `check_progress` does.
_MAX_TEXT_CHARS = 12000


def _within(text: str, budget: int | None) -> str:
    if budget is None or len(text) <= budget:
        return text
    return text[:budget] + "\n\n[...cut here: you have not seen the rest...]"


def _context_lines(ctx: dict[str, Any]) -> list[str]:
    lines = [
        f"Thesis topic: {ctx.get('current_topic') or 'not settled yet'}",
        f"Field of study: {ctx.get('field_of_study') or 'unspecified'}",
        f"This part of the thesis: {ctx.get('part_name') or 'unnamed'}",
        f"Round: {ctx.get('round_number', 1)}",
    ]
    others = cast(list[dict[str, str]], ctx.get("other_parts") or [])
    if others:
        names = ", ".join(f"{p['name']} ({p['state']})" for p in others)
        lines.append(f"Other parts of the thesis, and where they stand: {names}")
    notes = cast(list[str], ctx.get("recent_notes") or [])
    if notes:
        lines.append("Recent meeting notes:\n" + "\n---\n".join(notes))
    return lines


def _user_message(ctx: dict[str, Any]) -> str:
    previous_text = str(ctx.get("previous_text") or "")
    budget = reading_budget(_MAX_TEXT_CHARS)
    if budget is not None and previous_text:
        budget //= 2

    lines = _context_lines(ctx)
    if ctx.get("previous_feedback") or ctx.get("previous_verdict"):
        lines.append(
            "The supervisor's feedback on the previous round "
            f"({ctx.get('previous_verdict') or 'no verdict'}):\n"
            f"{ctx.get('previous_feedback') or '(no comment)'}"
        )
    if previous_text:
        lines.append(f"The previous round's text:\n{_within(previous_text, budget)}")
    lines.append(f"The fragment:\n{_within(str(ctx.get('text', '')), budget)}")
    if ctx.get("detail"):
        lines.append(f"The supervisor asks: {ctx['detail']}")
    return "\n\n".join(lines)


def _grounded(
    changes: list[FragmentChangeReply], text: str
) -> list[FragmentChangeReply]:
    """Keep the changes whose quote is really there, up to the limit.

    Checked before the limit: a dropped item must not cost a real one its
    place. `grounding.verify_findings` is for findings with severities, which
    this action deliberately has not got.
    """
    fragment = ThesisText(text)
    kept = [c for c in changes if fragment.contains(c.quote)]
    if len(kept) < len(changes):
        logger.info(
            "fragment_changes_ungrounded", dropped=len(changes) - len(kept)
        )
    return kept[: prompts.MAX_CHANGES]


def _direction(
    direction: str,
    changes: list[FragmentChangeReply],
    additions: list[str],
) -> str:
    """A direction that needs work names the work; without any, it is on track.

    The gentle default again: grounding may have dropped the one thing the
    model wanted changed.
    """
    if direction == "needs_changes" and not changes:
        return "on_track"
    if direction == "needs_additions" and not additions:
        return "on_track"
    return direction


def review_fragment(state: ActionState) -> ActionState:
    """Summarise a fragment and draft the supervisor's formative feedback."""
    try:
        ctx = state["context"]
        text = str(ctx.get("text", ""))
        if not text.strip():
            raise ValueError("no fragment to read")

        llm = get_llm(state["model"])
        reply = invoke_structured(
            llm,
            [
                SystemMessage(  # type: ignore[attr-defined]
                    content=prompts.get_system_prompt(state.get("language", "pl"))
                ),
                HumanMessage(content=_user_message(ctx)),
            ],
            FRAGMENT_REVIEW,
            node="review_fragment",
        )

        changes = _grounded(reply.changes, text)
        additions = reply.additions[: prompts.MAX_ADDITIONS]
        logger.info(
            "review_fragment_complete",
            action_id=state["action_id"],
            direction=reply.direction,
            changes=len(changes),
            additions=len(additions),
        )
        result: ActionState = state.copy()
        result["output"] = {
            "summary": reply.summary,
            "answer": reply.answer,
            "direction": _direction(reply.direction, changes, additions),
            "strengths": reply.strengths,
            "changes": [c.model_dump() for c in changes],
            "additions": additions,
            "addressed": reply.addressed,
            "next_step": reply.next_step,
        }
        result["status"] = "fragment_reviewed"
        result["error"] = None
        return result
    except Exception as exc:
        raise_if_provider_error(exc)
        logger.error("review_fragment_failed", error=str(exc))
        result = state.copy()
        result["error"] = str(exc)
        return result
