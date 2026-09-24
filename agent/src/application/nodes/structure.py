"""LangGraph node: analyze thesis chapter structure and coherence."""

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from src.application.excerpt import render_document_block
from src.application.json_output import parse_json_array
from src.application.prompts import structure as prompts
from src.domain.analysis import Finding, FindingSeverity, FindingSource
from src.infrastructure.llm_factory import get_llm

from ..state import ActionState, AnalysisUpdate

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# How much of the thesis this node reads. The map that travels with the
# excerpt covers what falls outside it — see `excerpt.render_document_block`.
_HEAD_CHARS = 30000


def analyze_structure(state: ActionState) -> AnalysisUpdate:
    """Analyze chapter structure and extend state with structural findings."""
    try:
        ctx = state["context"]
        llm = get_llm(state["model"])
        document = render_document_block(ctx, head_chars=_HEAD_CHARS)
        messages = [
            SystemMessage(  # type: ignore[attr-defined]
                content=prompts.get_system_prompt(state.get("language", "pl"))
            ),
            # No guidelines: whether required elements are there and follow
            # the rules is `check_requirements`' call. Handed the same rubric,
            # this node reported the same missing chapter a second time.
            HumanMessage(content=document),
        ]
        response = llm.invoke(messages)
        data = parse_json_array(response.content)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        new_findings: list[Finding] = [
            Finding(
                section=item["section"],
                description=item["description"],
                severity=FindingSeverity(item["severity"]),
                suggestion=item["suggestion"],
                source=FindingSource.STRUCTURE,
            )
            for item in data
        ]
        logger.info("structure_analysis_complete", finding_count=len(new_findings))
        return {"findings": new_findings}
    except Exception as exc:
        logger.error("structure_analysis_failed", error=str(exc))
        return {"node_errors": [f"structure: {exc}"]}
