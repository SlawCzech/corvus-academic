"""LangGraph nodes: does every work the thesis cites exist?

The one action where an agent — a model deciding its own next step, with
tools — earns its place. The graph around it keeps it small:

    extract_references → match_references ─┬→ report
                                            └→ investigate ⇄ tools → report

- `extract_references`: the model lists the entries (structured output).
- `match_references`: no model. Each entry goes to Crossref once; a match on
  title, year and first author settles it, a URL marks netography. Most of
  a bibliography ends here.
- `investigate` ⇄ `tools`: the ReAct loop, as two nodes and a conditional
  edge — the model either asks for a tool (the edge goes to `tools`, whose
  result comes back to `investigate`) or stops (the edge goes on). It only
  sees what the deterministic step left, and it has a budget of tool calls:
  when it is spent, the model is asked once more without tools.
- `report`: one structured call turns the investigation into a verdict per
  reference, and the output is assembled.

Only reference strings reach Crossref; the thesis text never leaves.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, cast

import structlog
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import tool  # pyright: ignore[reportUnknownVariableType]
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from src.application.bibliography import (
    NOT_INDEXED,
    SUSPICIOUS,
    UNCHECKED,
    UNRESOLVED,
    VERIFIED,
    WEBSITE,
    Check,
    bibliography_section,
    doi_in,
    is_website,
    match,
)
from src.application.json_output import message_text
from src.application.prompts import bibliography as prompts
from src.application.replies import REFERENCES, VERDICTS
from src.application.structured import invoke_structured
from src.infrastructure.crossref import CrossrefClient, CrossrefUnavailableError
from src.infrastructure.llm_factory import get_llm

from ..state import ActionState

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Past this, the rest of the list is not checked (and says so).
_MAX_REFERENCES = 80
# Tool calls the agent may make across all the references it investigates.
TOOL_BUDGET = 12


class BibliographyState(ActionState, total=False):
    """The action state, plus what this action builds on the way."""

    references: list[dict[str, Any]]
    checks: list[dict[str, str]]
    # The agent's conversation. `add_messages` appends — and replaces a
    # message whose id it already holds — which is what a ReAct loop needs.
    messages: Annotated[list[AnyMessage], add_messages]


# ---------- tools ----------


@tool
def search_crossref(query: str) -> str:
    """Search Crossref for works matching a reference, a title, or author + title.

    Returns up to five records, one per line: doi, year, authors, title,
    venue, type, relevance score.
    """
    try:
        works = CrossrefClient().search(query, rows=5)
    except CrossrefUnavailableError as exc:
        return f"Crossref unavailable: {exc}"
    return "\n".join(w.describe() for w in works) or "no records"


@tool
def lookup_doi(doi: str) -> str:
    """Resolve a DOI in Crossref. Returns its record, or says it does not exist."""
    try:
        work = CrossrefClient().lookup(doi)
    except CrossrefUnavailableError as exc:
        return f"Crossref unavailable: {exc}"
    return work.describe() if work else f"no Crossref record for DOI {doi}"


TOOLS = [search_crossref, lookup_doi]
tools = ToolNode(TOOLS)


# ---------- nodes ----------


def extract_references(state: BibliographyState) -> dict[str, Any]:
    """List the bibliography's entries."""
    ctx = state["context"]
    raw_map = ctx.get("document_map")
    section = bibliography_section(
        str(ctx.get("text", "")),
        cast(dict[str, Any], raw_map) if isinstance(raw_map, dict) else {},
    )
    if not section:
        return {"error": "no bibliography found in the thesis"}
    try:
        reply = invoke_structured(
            get_llm(state["model"]),
            [SystemMessage(content=prompts.EXTRACT), HumanMessage(content=section)],
            REFERENCES,
            node="extract_references",
        )
    except Exception as exc:
        logger.error("reference_extraction_failed", error=str(exc))
        return {"error": str(exc)}
    references = [r.model_dump() for r in reply.references]
    logger.info("references_extracted", count=len(references))
    return {"references": references}


def match_references(state: BibliographyState) -> dict[str, Any]:
    """Settle what Crossref can settle without judgement."""
    references = state.get("references") or []
    client = CrossrefClient()
    checks: list[dict[str, str]] = []
    for index, ref in enumerate(references):
        entry = str(ref.get("entry", ""))
        if index >= _MAX_REFERENCES:
            check = Check(UNCHECKED, note="poza limitem sprawdzanych pozycji")
        elif is_website(entry):
            check = Check(WEBSITE)
        else:
            try:
                check = match(
                    entry, cast(int | None, ref.get("year")), client.search(entry)
                )
            except CrossrefUnavailableError as exc:
                check = Check(UNCHECKED, note=f"Crossref niedostępny: {exc}")
        checks.append({"status": check.status, "note": check.note, "doi": check.doi})
    logger.info(
        "references_matched",
        verified=sum(c["status"] == VERIFIED for c in checks),
        unresolved=sum(c["status"] == UNRESOLVED for c in checks),
    )
    return {"checks": checks}


def after_matching(state: BibliographyState) -> Literal["investigate", "report"]:
    """The agent only runs when the deterministic step left something open."""
    checks = state.get("checks") or []
    return "investigate" if any(c["status"] == UNRESOLVED for c in checks) else "report"


def _open_references(state: BibliographyState) -> list[tuple[int, str]]:
    references = state.get("references") or []
    checks = state.get("checks") or []
    return [
        (i, str(references[i].get("entry", "")))
        for i, c in enumerate(checks)
        if c["status"] == UNRESOLVED
    ]


def investigate(state: BibliographyState) -> dict[str, Any]:
    """One turn of the agent: ask for a tool, or stop."""
    messages = list(state.get("messages") or [])
    new: list[AnyMessage] = []
    if not messages:
        listing = "\n".join(
            f"[{i}] {entry}"
            + (f"  (DOI in entry: {doi_in(entry)})" if doi_in(entry) else "")
            for i, entry in _open_references(state)
        )
        new = [
            SystemMessage(content=prompts.INVESTIGATE.format(budget=TOOL_BUDGET)),
            HumanMessage(content=f"References to check:\n{listing}"),
        ]
        messages = new
    used = sum(isinstance(m, ToolMessage) for m in messages)
    llm = get_llm(state["model"])
    # Out of budget: the same model, without tools, has to wrap up.
    model = llm if used >= TOOL_BUDGET else llm.bind_tools(TOOLS)  # pyright: ignore[reportUnknownMemberType]
    try:
        reply = model.invoke(messages)
    except Exception as exc:
        logger.error("bibliography_agent_failed", error=str(exc))
        reply = AIMessage(content=f"(the investigation stopped: {exc})")
    return {"messages": [*new, reply]}


def after_investigating(state: BibliographyState) -> Literal["tools", "report"]:
    """The ReAct edge: a tool call goes to the tools, anything else ends the loop."""
    messages = state.get("messages") or []
    last = messages[-1] if messages else None
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return "report"


def _transcript(messages: list[AnyMessage]) -> str:
    lines: list[str] = []
    for m in messages:
        if isinstance(m, SystemMessage):
            continue
        if isinstance(m, AIMessage) and m.tool_calls:
            for call in m.tool_calls:
                lines.append(f"CALL {call['name']}({call['args']})")
        elif isinstance(m, ToolMessage):
            lines.append(f"RESULT {message_text(m.content)}")  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        else:
            lines.append(message_text(m.content))  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
    return "\n".join(lines)


def report(state: BibliographyState) -> dict[str, Any]:
    """Verdicts for what the agent investigated, and the action's output."""
    if state.get("error"):
        return {}
    references = state.get("references") or []
    checks = [dict(c) for c in state.get("checks") or []]
    open_refs = _open_references(state)
    messages = state.get("messages") or []

    if open_refs and messages:
        language = prompts.LANGUAGE_NAMES.get(state.get("language", "pl"), "Polish")
        try:
            reply = invoke_structured(
                get_llm(state["model"]),
                [
                    SystemMessage(content=prompts.VERDICTS.format(language=language)),
                    HumanMessage(content=_transcript(messages)),
                ],
                VERDICTS,
                node="bibliography_report",
            )
            by_index = {v.index: v for v in reply.verdicts}
        except Exception as exc:
            logger.error("bibliography_verdicts_failed", error=str(exc))
            by_index = {}
        for index, _ in open_refs:
            verdict = by_index.get(index)
            if verdict is None:
                checks[index] = {
                    "status": UNCHECKED,
                    "note": "bez rozstrzygnięcia",
                    "doi": "",
                }
                continue
            status = VERIFIED if verdict.status == "found" else verdict.status
            checks[index] = {"status": status, "note": verdict.note, "doi": verdict.doi}

    rows = [
        {
            "entry": str(ref.get("entry", "")),
            "status": checks[i]["status"] if i < len(checks) else UNCHECKED,
            "note": checks[i]["note"] if i < len(checks) else "",
            "doi": checks[i]["doi"] if i < len(checks) else "",
        }
        for i, ref in enumerate(references)
    ]
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    logger.info("bibliography_checked", **counts)
    return {
        "output": {
            "references": rows,
            "counts": counts,
            "suspicious": counts.get(SUSPICIOUS, 0),
            "not_indexed": counts.get(NOT_INDEXED, 0),
            "websites": counts.get(WEBSITE, 0),
        },
        "status": "bibliography_checked",
        "error": None,
    }
