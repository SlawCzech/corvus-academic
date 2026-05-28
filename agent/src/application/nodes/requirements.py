"""LangGraph node: check conformance with university guidelines."""

import json
from collections.abc import Sequence

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from src.domain.analysis import Finding, FindingSeverity
from src.infrastructure.llm_factory import get_llm

from ..state import AnalysisState

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are a thesis reviewer checking whether a diploma thesis conforms to the "
    "provided university and promoter guidelines. For each violated or missing "
    "requirement produce a finding. Return your findings as a JSON array. "
    "Each element must have these fields: "
    "section (str), description (str), "
    "severity (one of: critical, major, minor), suggestion (str). "
    "Return only the raw JSON array — no markdown, no explanation. "
    "Return an empty JSON array [] if the thesis fully conforms to all requirements."
)


def check_requirements(state: AnalysisState) -> AnalysisState:
    """Check conformance with university guidelines using guidelines text from state."""
    try:
        llm = get_llm()
        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Thesis text:\n{state['text']}\n\n"
                    f"Requirements / Guidelines:\n{state['guidelines']}"
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
        logger.info("requirements_check_complete", finding_count=len(new_findings))
        result: AnalysisState = state.copy()
        result["findings"] = state["findings"] + new_findings
        result["error"] = None
        return result
    except Exception as exc:
        logger.error("requirements_check_failed", error=str(exc))
        result = state.copy()
        result["error"] = str(exc)
        return result
