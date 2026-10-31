"""LangGraph graph definitions — one builder per action type."""

# LangGraph's add_node/compile overloads reference CachePolicy[Unknown] internally,
# which makes every call site reportUnknownMemberType. All other project code is
# fully typed — this suppression is scoped to this file only.
# pyright: reportUnknownMemberType=false

from typing import Any, cast

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.domain.action import ActionType
from src.infrastructure.settings import settings

from .nodes.bibliography import (
    BibliographyState,
    after_investigating,
    after_matching,
    extract_references,
    investigate,
    match_references,
    report,
    tools,
)
from .nodes.check_progress import check_progress
from .nodes.coherence import (
    ChapterTask,
    check_coherence,
    digest_chapter,
    route_chapters,
)
from .nodes.defence_questions import defence_questions
from .nodes.draft_meeting_note import draft_meeting_note
from .nodes.methodology import analyze_methodology
from .nodes.promoter_review import promoter_review
from .nodes.propose_topic import propose_topic
from .nodes.requirements import check_requirements
from .nodes.review import generate_review
from .nodes.review_fragment import review_fragment
from .nodes.structure import analyze_structure
from .nodes.verify import verify
from .state import ActionState

CompiledActionGraph = CompiledStateGraph[ActionState, None, Any, Any]

# Every action the agent can run. The API checks against this before queueing
# anything, so an unknown action type fails at the request, not in a worker.
IMPLEMENTED_ACTIONS: frozenset[str] = frozenset(ActionType)


def build_analysis_graph(
    mode: str = "full", checkpointer: BaseCheckpointSaver[Any] | None = None
) -> CompiledActionGraph:
    """Build and compile the full thesis analysis graph for the given mode.

    mode="full"        — structure, methodology and requirements in parallel
                         with one digest per chapter; the coherence check
                         once the digests are in; `verify` once all four
                         analyses are done; the promoter's pick of findings
                         (if asked); the review
    mode="review_only" — review only (no intermediate finding nodes)

    The three analysis nodes read the thesis and the guidelines, never each
    other's findings, so nothing but habit ran them one after another. In
    parallel the review waits for the slowest of them instead of their sum.
    """
    builder: StateGraph[ActionState, None, Any, Any] = StateGraph(ActionState)

    if mode == "review_only":
        builder.add_node("generate_review", generate_review)
        builder.add_edge(START, "generate_review")
        builder.add_edge("generate_review", END)
    else:
        builder.add_node("analyze_structure", analyze_structure)
        builder.add_node("analyze_methodology", analyze_methodology)
        builder.add_node("check_requirements", check_requirements)
        # Its input is the `Send` payload — one chapter — not the graph state.
        # (Any: pyright cannot match a TypedDict class to `type[NodeInputT]`.)
        builder.add_node(
            "digest_chapter", cast(Any, digest_chapter), input_schema=ChapterTask
        )
        builder.add_node("check_coherence", check_coherence)
        builder.add_node("verify", verify)
        builder.add_node("promoter_review", promoter_review)
        builder.add_node("generate_review", generate_review)
        prefix_readers = [
            "analyze_structure",
            "analyze_methodology",
            "check_requirements",
        ]
        for node in prefix_readers:
            builder.add_edge(START, node)
        # Map-reduce over the body: one `digest_chapter` per chapter, decided
        # at run time by `route_chapters` (a `Send` each), then one
        # `check_coherence` over all the digests. The listed targets are the
        # places the router may send to.
        analysis = list(prefix_readers)
        if settings.review_chapter_digests:
            builder.add_conditional_edges(
                START, route_chapters, ["digest_chapter", "check_coherence"]
            )
            builder.add_edge("digest_chapter", "check_coherence")
            analysis.append("check_coherence")
        # A list as the source makes this a join: `verify` runs once, after
        # every branch has written its findings (or its error) to state —
        # the first point where they can be checked against each other.
        builder.add_edge(analysis, "verify")
        # Where the run pauses when the promoter wants to see the findings
        # before the review is written — a pass-through otherwise.
        builder.add_edge("verify", "promoter_review")
        builder.add_edge("promoter_review", "generate_review")
        builder.add_edge("generate_review", END)

    return builder.compile(checkpointer=checkpointer)


def _build_single_node_graph(
    name: str,
    node: Any,  # noqa: ANN401  — LangGraph node callables are untyped
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> CompiledActionGraph:
    """Compile a one-node graph — the shape most actions need."""
    builder: StateGraph[ActionState, None, Any, Any] = StateGraph(ActionState)
    builder.add_node(name, node)
    builder.add_edge(START, name)
    builder.add_edge(name, END)
    return builder.compile(checkpointer=checkpointer)


def _build_checked_analysis_graph(
    name: str,
    node: Any,  # noqa: ANN401  — LangGraph node callables are untyped
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> CompiledActionGraph:
    """One analysis node, its findings verified before they are returned."""
    builder: StateGraph[ActionState, None, Any, Any] = StateGraph(ActionState)
    builder.add_node(name, node)
    builder.add_node("verify", verify)
    builder.add_edge(START, name)
    builder.add_edge(name, "verify")
    builder.add_edge("verify", END)
    return builder.compile(checkpointer=checkpointer)


def _after_extracting(state: BibliographyState) -> str:
    return END if state.get("error") else "match_references"


def build_bibliography_graph(
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> CompiledActionGraph:
    """Extract, match deterministically, let the agent take what is left, report.

    The agent is two nodes and a conditional edge — `investigate` asks for a
    tool or stops, `tools` runs it and hands the result back. That cycle is
    the whole of what "an agent" is here; see `nodes/bibliography.py`.
    """
    builder: StateGraph[BibliographyState, None, Any, Any] = StateGraph(
        BibliographyState
    )
    builder.add_node("extract_references", extract_references)
    builder.add_node("match_references", match_references)
    builder.add_node("investigate", investigate)
    builder.add_node("tools", tools)
    builder.add_node("report", report)
    builder.add_edge(START, "extract_references")
    builder.add_conditional_edges(
        "extract_references", _after_extracting, ["match_references", END]
    )
    builder.add_conditional_edges(
        "match_references", after_matching, ["investigate", "report"]
    )
    builder.add_conditional_edges(
        "investigate", after_investigating, ["tools", "report"]
    )
    builder.add_edge("tools", "investigate")
    builder.add_edge("report", END)
    # The action state is a subset of this one; callers only read those keys.
    return cast(CompiledActionGraph, builder.compile(checkpointer=checkpointer))


def build_action_graph(
    action_type: str,
    mode: str = "full",
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> CompiledActionGraph:
    """Return the compiled graph that runs the given action.

    `generate_review` delegates to the four-node pipeline unchanged — it
    already *is* the final action. Every other action is one node: that is the
    point of the shared state, and it is why adding an action means adding a
    node and a prompt rather than a pipeline.

    With a checkpointer the graph saves its state after every step and can
    resume a run under the same ``thread_id`` — see `infrastructure.checkpoints`.
    """
    match action_type:
        case ActionType.GENERATE_REVIEW:
            return build_analysis_graph(mode=mode, checkpointer=checkpointer)
        case ActionType.PROPOSE_TOPIC:
            return _build_single_node_graph(
                "propose_topic", propose_topic, checkpointer
            )
        case ActionType.EVALUATE_METHODOLOGY:
            # The same node the full review runs, checked the same way.
            return _build_checked_analysis_graph(
                "analyze_methodology", analyze_methodology, checkpointer
            )
        case ActionType.CHECK_PROGRESS:
            return _build_single_node_graph(
                "check_progress", check_progress, checkpointer
            )
        case ActionType.DRAFT_MEETING_NOTE:
            return _build_single_node_graph(
                "draft_meeting_note", draft_meeting_note, checkpointer
            )
        case ActionType.VERIFY_BIBLIOGRAPHY:
            return build_bibliography_graph(checkpointer)
        case ActionType.DEFENCE_QUESTIONS:
            return _build_single_node_graph(
                "defence_questions", defence_questions, checkpointer
            )
        case ActionType.REVIEW_FRAGMENT:
            return _build_single_node_graph(
                "review_fragment", review_fragment, checkpointer
            )
        case _:
            raise ValueError(f"No graph for action type: {action_type!r}")
