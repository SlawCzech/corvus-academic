"""LangGraph node: analyze thesis methodology and bibliography."""

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from src.application.excerpt import render_document_block
from src.application.json_output import parse_json_array
from src.application.prompts import methodology as prompts
from src.domain.analysis import Finding, FindingSeverity, FindingSource
from src.infrastructure.llm_factory import get_llm

from ..state import ActionState, AnalysisUpdate

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# How much of the thesis this node reads. The map that travels with the
# excerpt covers what falls outside it — see `excerpt.render_document_block`.
_HEAD_CHARS = 30000


def analyze_methodology(state: ActionState) -> AnalysisUpdate:
    """Analyze methodology and bibliography, extend state with methodology findings."""
    try:
        ctx = state["context"]
        llm = get_llm(state["model"])
        document = render_document_block(ctx, head_chars=_HEAD_CHARS)
        messages = [
            SystemMessage(  # type: ignore[attr-defined]
                content=prompts.get_system_prompt(state.get("language", "pl"))
            ),
            HumanMessage(
                content=(f"{document}\n\nGuidelines:\n{ctx.get('guidelines', '')}")
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
                source=FindingSource.METHODOLOGY,
            )
            for item in data
        ]
        logger.info("methodology_analysis_complete", finding_count=len(new_findings))
        return {"findings": new_findings}
    except Exception as exc:
        logger.error("methodology_analysis_failed", error=str(exc))
        return {"node_errors": [f"methodology: {exc}"]}
