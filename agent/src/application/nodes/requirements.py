"""LangGraph node: check conformance with university guidelines."""

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from src.application.excerpt import render_document_block
from src.application.prompts.scopes import scope_instruction
from src.application.replies import FINDINGS
from src.application.structured import invoke_structured
from src.domain.analysis import Finding, FindingSeverity, FindingSource
from src.infrastructure.llm_factory import get_llm

from ..state import ActionState, AnalysisUpdate

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# How much of the thesis this node reads. The map that travels with the
# excerpt covers what falls outside it — see `excerpt.render_document_block`.
_HEAD_CHARS = 30000

_SYSTEM_PROMPT_BASE = """You are checking a thesis against university requirements.

The requirements document is provided below. Check each requirement
systematically. For each violation found, create a Finding with:
- section: the specific requirement section (e.g. "1.4 Introduction")
- description: what is missing or incorrect
- severity: use ONLY the severity rules defined in section 4
  of the requirements document
- suggestion: concrete corrective action

Return ONLY a JSON array of findings:
[
  {{
    "section": "<requirement section reference>",
    "description": "<what is missing or wrong>",
    "severity": "critical" | "major" | "minor",
    "suggestion": "<concrete corrective action>"
  }}
]

If no violations found, return an empty array: []
Return raw JSON only — no markdown, no explanation.

The thesis text may be an excerpt. The document map that comes with it was
computed from the complete thesis: a section it lists EXISTS. Never raise a
finding that a section is missing when the map lists it, and never treat the
end of the excerpt as the end of the thesis.

When a requirement concerns the quality of the research or of the argument
rather than an element or a rule you can check, check only that what it asks
for is there; how well it is done is judged by the other analyses.
{scope_instruction}
{lang_instruction}"""

_LANG_INSTRUCTIONS = {
    "pl": "Write all text fields (section, description, suggestion) in Polish.",
    "en": "Write all text fields (section, description, suggestion) in English.",
}


def _get_system_prompt(language: str = "pl") -> str:
    return _SYSTEM_PROMPT_BASE.format(
        scope_instruction=scope_instruction(FindingSource.REQUIREMENTS),
        lang_instruction=_LANG_INSTRUCTIONS.get(language, _LANG_INSTRUCTIONS["pl"]),
    )


def check_requirements(state: ActionState) -> AnalysisUpdate:
    """Check thesis conformance against university guidelines from state."""
    try:
        ctx = state["context"]
        llm = get_llm(state["model"])
        messages = [
            SystemMessage(content=_get_system_prompt(state.get("language", "pl"))),  # type: ignore[attr-defined]
            HumanMessage(
                content=(
                    f"University requirements:\n{ctx.get('guidelines', '')}\n\n"
                    f"{render_document_block(ctx, head_chars=_HEAD_CHARS)}"
                )
            ),
        ]
        data = invoke_structured(llm, messages, FINDINGS, node="requirements")
        new_findings: list[Finding] = [
            Finding(
                section=item.section,
                description=item.description,
                severity=FindingSeverity(item.severity),
                suggestion=item.suggestion,
                source=FindingSource.REQUIREMENTS,
                quote=item.quote.strip(),
            )
            for item in data
        ]
        logger.info(
            "requirements_check_complete",
            finding_count=len(new_findings),
            critical=sum(
                1 for f in new_findings if f.severity == FindingSeverity.CRITICAL
            ),
        )
        return {"findings": new_findings}
    except Exception as exc:
        logger.error("requirements_check_failed", error=str(exc))
        return {"node_errors": [f"requirements: {exc}"]}
