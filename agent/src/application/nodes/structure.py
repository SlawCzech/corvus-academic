"""LangGraph node: analyze thesis chapter structure and coherence."""

import json
from collections.abc import Sequence

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from src.application.prompts import structure as prompts
from src.domain.analysis import Finding, FindingSeverity
from src.infrastructure.llm_factory import get_llm

from ..state import AnalysisState

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def analyze_structure(state: AnalysisState) -> AnalysisState:
    """Analyze chapter structure and extend state with structural findings."""
    try:
        llm = get_llm()
        messages = [
            SystemMessage(content=prompts.SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Thesis text:\n{state['text']}\n\n"
                    f"Guidelines:\n{state['guidelines']}"
                )
            ),
        ]
        response = llm.invoke(messages)
        # BaseChatModel.invoke() returns BaseMessage; .content is str | list[…|dict]
        # where the dict value types are Unknown in LangChain's type stubs.
        raw: str | Sequence[object] = response.content  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        content: str = raw if isinstance(raw, str) else json.dumps(raw)
        data: list[dict[str, str]] = json.loads(content)
        new_findings: list[Finding] = [
            Finding(
                section=item["section"],
                description=item["description"],
                severity=FindingSeverity(item["severity"]),
                suggestion=item["suggestion"],
            )
            for item in data
        ]
        logger.info("structure_analysis_complete", finding_count=len(new_findings))
        result: AnalysisState = state.copy()
        result["findings"] = state["findings"] + new_findings
        result["error"] = None
        return result
    except Exception as exc:
        logger.error("structure_analysis_failed", error=str(exc))
        result = state.copy()
        result["error"] = str(exc)
        return result
