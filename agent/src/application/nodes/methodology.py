"""LangGraph node: analyze thesis methodology and bibliography."""

import json
from collections.abc import Sequence

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from src.application.prompts import methodology as prompts
from src.domain.analysis import Finding, FindingSeverity
from src.infrastructure.llm_factory import get_llm

from ..state import AnalysisState

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def analyze_methodology(state: AnalysisState) -> AnalysisState:
    """Analyze methodology and bibliography, extend state with methodology findings."""
    try:
        llm = get_llm(state["model"])
        max_chars = 12000
        thesis_text = state["text"][:max_chars]
        messages = [
            SystemMessage(content=prompts.SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Thesis text:\n{thesis_text}\n\n"
                    f"Guidelines:\n{state['guidelines']}"
                )
            ),
        ]
        response = llm.invoke(messages)
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
        logger.info("methodology_analysis_complete", finding_count=len(new_findings))
        result: AnalysisState = state.copy()
        result["findings"] = state["findings"] + new_findings
        result["error"] = None
        return result
    except Exception as exc:
        logger.error("methodology_analysis_failed", error=str(exc))
        result = state.copy()
        result["error"] = str(exc)
        return result
