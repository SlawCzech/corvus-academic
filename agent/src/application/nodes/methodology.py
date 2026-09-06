"""LangGraph node: analyze thesis methodology and bibliography."""

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from src.application.json_output import parse_json_array
from src.application.prompts import methodology as prompts
from src.domain.analysis import Finding, FindingSeverity
from src.infrastructure.llm_factory import get_llm

from ..state import ActionState

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def analyze_methodology(state: ActionState) -> ActionState:
    """Analyze methodology and bibliography, extend state with methodology findings."""
    try:
        ctx = state["context"]
        llm = get_llm(state["model"])
        max_chars = 12000
        thesis_text = str(ctx.get("text", ""))[:max_chars]
        messages = [
            SystemMessage(  # type: ignore[attr-defined]
                content=prompts.get_system_prompt(state.get("language", "pl"))
            ),
            HumanMessage(
                content=(
                    f"Thesis text:\n{thesis_text}\n\n"
                    f"Guidelines:\n{ctx.get('guidelines', '')}"
                )
            ),
        ]
        response = llm.invoke(messages)
        data = parse_json_array(response.content)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        new_findings: list[Finding] = [
            Finding(
                section=item["section"],
                description=item["description"],
                severity=FindingSeverity(item["severity"]),
                suggestion=item["suggestion"],
            )
            for item in data
        ]
        logger.info("methodology_analysis_complete", finding_count=len(new_findings))
        result: ActionState = state.copy()
        result["findings"] = state["findings"] + new_findings
        result["error"] = None
        return result
    except Exception as exc:
        logger.error("methodology_analysis_failed", error=str(exc))
        result = state.copy()
        result["error"] = str(exc)
        return result
