"""LangGraph node: turn a trial review into a mail to the student.

Reads the review and its findings, never the thesis: the promoter already paid
for that reading, and a mail must not say what the review did not (ADR 0019).
The mail is a draft. Corvus sends nothing; the promoter copies it.
"""

from typing import Any, cast

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from src.application.prompts import student_email as prompts
from src.application.replies import STUDENT_EMAIL
from src.application.structured import invoke_structured
from src.infrastructure.llm_factory import get_llm
from src.infrastructure.provider_errors import raise_if_provider_error

from ..state import ActionState

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _finding_line(finding: dict[str, Any]) -> str:
    line = (
        f"- [{finding.get('severity', '')}] {finding.get('section', '')}: "
        f"{finding.get('description', '')}"
    )
    suggestion = finding.get("suggestion")
    return f"{line} Suggestion: {suggestion}" if suggestion else line


def _user_message(ctx: dict[str, Any]) -> str:
    findings = cast(list[dict[str, Any]], ctx.get("findings") or [])
    lines: list[str] = []
    if ctx.get("current_topic"):
        lines.append(f"Thesis topic: {ctx['current_topic']}")
    lines.append(f"Trial review:\n{ctx.get('review_text', '')}")
    lines.append(
        "Findings behind it:\n"
        + ("\n".join(_finding_line(f) for f in findings) or "None")
    )
    if str(ctx.get("detail") or "").strip():
        lines.append(f"A word from the supervisor:\n{ctx['detail']}")
    return "\n\n".join(lines)


def draft_student_email(state: ActionState) -> ActionState:
    """Draft the mail the promoter will read, change and send themselves."""
    try:
        ctx = state["context"]
        if not str(ctx.get("review_text", "")).strip():
            raise ValueError("no trial review to write from")

        llm = get_llm(state["model"])
        reply = invoke_structured(
            llm,
            [
                SystemMessage(  # type: ignore[attr-defined]
                    content=prompts.get_system_prompt(state.get("language", "pl"))
                ),
                HumanMessage(content=_user_message(ctx)),
            ],
            STUDENT_EMAIL,
            node="draft_student_email",
        )

        logger.info("draft_student_email_complete", action_id=state["action_id"])
        result: ActionState = state.copy()
        result["output"] = {"subject": reply.subject, "body": reply.body}
        result["status"] = "drafted"
        result["error"] = None
        return result
    except Exception as exc:
        raise_if_provider_error(exc)
        logger.error("draft_student_email_failed", error=str(exc))
        result = state.copy()
        result["error"] = str(exc)
        return result
