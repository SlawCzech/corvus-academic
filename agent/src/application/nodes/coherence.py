"""LangGraph nodes: does the thesis hold together — map over chapters, then reduce.

Three pieces, and the part of LangGraph each one is about:

- `route_chapters` runs on the edge out of START and returns one `Send` per
  chapter. `Send` is a dynamic fan-out: the number of branches is decided by
  the data at run time, not drawn in the graph — a thesis with seven chapters
  gets seven `digest_chapter` runs, in parallel with the three analyses.
- `digest_chapter` gets its `Send` payload as its whole input — one chapter,
  not the graph state — and returns a digest. Digests from every branch are
  summed into ``chapter_digests`` by that key's reducer.
- `check_coherence` runs once all digests are in and reads them side by side
  with the introduction and the conclusions. That comparison is what no
  single prefix-reading node could make: the results chapter and the
  conclusions that should follow from it are rarely in the same 30 thousand
  characters.

A thesis without a usable document map gets no fan-out: the edge goes straight
to `check_coherence`, which then has nothing to compare and returns nothing.
"""

from __future__ import annotations

from typing import Any, cast

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import Send
from typing_extensions import TypedDict

from src.application.chapters import frame, split_chapters
from src.application.prompts import coherence as prompts
from src.application.replies import DIGEST, FINDINGS
from src.application.structured import invoke_structured
from src.domain.analysis import Finding, FindingSeverity, FindingSource
from src.infrastructure.llm_factory import get_llm

from ..state import ActionState, AnalysisUpdate

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class ChapterTask(TypedDict):
    """What one `digest_chapter` branch is sent: its chapter, nothing more."""

    index: int
    title: str
    text: str
    model: str
    language: str


class DigestUpdate(TypedDict, total=False):
    chapter_digests: list[dict[str, Any]]
    node_errors: list[str]


def _map(ctx: dict[str, Any]) -> dict[str, Any]:
    raw = ctx.get("document_map")
    return cast(dict[str, Any], raw) if isinstance(raw, dict) else {}


def route_chapters(state: ActionState) -> list[Send] | list[str]:
    """One `digest_chapter` per body chapter — or straight on, if there are none."""
    ctx = state["context"]
    chapters = split_chapters(str(ctx.get("text", "")), _map(ctx))
    if not chapters:
        return ["check_coherence"]
    logger.info("chapters_fanned_out", count=len(chapters))
    return [
        Send(
            "digest_chapter",
            ChapterTask(
                index=i,
                title=chapter.title,
                text=chapter.text,
                model=state["model"],
                language=state.get("language", "pl"),
            ),
        )
        for i, chapter in enumerate(chapters)
    ]


def digest_chapter(task: ChapterTask) -> DigestUpdate:
    """Record what one chapter says: a summary and its claims, quoted."""
    try:
        reply = invoke_structured(
            get_llm(task["model"]),
            [
                SystemMessage(content=prompts.digest_prompt(task["language"])),
                HumanMessage(content=f"## {task['title']}\n\n{task['text']}"),
            ],
            DIGEST,
            node="digest_chapter",
        )
    except Exception as exc:
        logger.error("chapter_digest_failed", chapter=task["title"], error=str(exc))
        return {"node_errors": [f"digest {task['title']}: {exc}"]}
    return {
        "chapter_digests": [
            {
                "index": task["index"],
                "title": task["title"],
                "summary": reply.summary,
                "claims": [c.model_dump() for c in reply.claims],
            }
        ]
    }


def _render_digests(digests: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for digest in sorted(digests, key=lambda d: int(d.get("index", 0))):
        lines.append(f"### {digest['title']}\n{digest['summary']}")
        for claim in cast(list[dict[str, str]], digest.get("claims", [])):
            quote = f" — „{claim['quote']}”" if claim.get("quote") else ""
            lines.append(f"- {claim['claim']}{quote}")
        lines.append("")
    return "\n".join(lines)


def check_coherence(state: ActionState) -> AnalysisUpdate:
    """Compare the chapters' digests with the introduction and the conclusions."""
    digests = state.get("chapter_digests") or []
    if not digests:
        return {}
    ctx = state["context"]
    text, document_map = str(ctx.get("text", "")), _map(ctx)
    introduction = frame(text, document_map, "introduction")
    conclusions = frame(text, document_map, "conclusions")
    try:
        replies = invoke_structured(
            get_llm(state["model"]),
            [
                SystemMessage(
                    content=prompts.coherence_prompt(state.get("language", "pl"))
                ),
                HumanMessage(
                    content=(
                        f"## Introduction\n\n{introduction or '(not found)'}\n\n"
                        f"## The body, part by part (digests)\n\n"
                        f"{_render_digests(digests)}\n"
                        f"## Conclusions\n\n{conclusions or '(not found)'}"
                    )
                ),
            ],
            FINDINGS,
            node="check_coherence",
        )
    except Exception as exc:
        logger.error("coherence_check_failed", error=str(exc))
        return {"node_errors": [f"coherence: {exc}"]}

    findings = [
        Finding(
            section=r.section,
            description=r.description,
            severity=FindingSeverity(r.severity),
            suggestion=r.suggestion,
            source=FindingSource.COHERENCE,
            quote=r.quote.strip(),
        )
        for r in replies
    ]
    logger.info(
        "coherence_check_complete", chapters=len(digests), finding_count=len(findings)
    )
    return {"findings": findings}
