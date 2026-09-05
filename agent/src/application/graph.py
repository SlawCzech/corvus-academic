"""LangGraph graph definitions — one builder per action type."""

# LangGraph's add_node/compile overloads reference CachePolicy[Unknown] internally,
# which makes every call site reportUnknownMemberType. All other project code is
# fully typed — this suppression is scoped to this file only.
# pyright: reportUnknownMemberType=false

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.domain.action import ActionType

from .nodes.methodology import analyze_methodology
from .nodes.propose_topic import propose_topic
from .nodes.requirements import check_requirements
from .nodes.review import generate_review
from .nodes.structure import analyze_structure
from .state import ActionState

CompiledActionGraph = CompiledStateGraph[ActionState, None, Any, Any]

# The actions that actually have a graph today. The other three land in
# Phase 3; until then the API rejects them instead of queueing work that can
# only fail in the worker.
IMPLEMENTED_ACTIONS: frozenset[str] = frozenset(
    {ActionType.GENERATE_REVIEW, ActionType.PROPOSE_TOPIC}
)


def build_analysis_graph(mode: str = "full") -> CompiledActionGraph:
    """Build and compile the full thesis analysis graph for the given mode.

    mode="full"        — structure → methodology → requirements → review
    mode="review_only" — review only (no intermediate finding nodes)
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
        builder.add_node("generate_review", generate_review)
        builder.add_edge(START, "analyze_structure")
        builder.add_edge("analyze_structure", "analyze_methodology")
        builder.add_edge("analyze_methodology", "check_requirements")
        builder.add_edge("check_requirements", "generate_review")
        builder.add_edge("generate_review", END)

    return builder.compile()


def _build_single_node_graph(
    name: str, node: Any  # noqa: ANN401  — LangGraph node callables are untyped
) -> CompiledActionGraph:
    """Compile a one-node graph — the shape most actions need."""
    builder: StateGraph[ActionState, None, Any, Any] = StateGraph(ActionState)
    builder.add_node(name, node)
    builder.add_edge(START, name)
    builder.add_edge(name, END)
    return builder.compile()


def build_action_graph(
    action_type: str, mode: str = "full"
) -> CompiledActionGraph:
    """Return the compiled graph that runs the given action.

    `generate_review` delegates to the existing four-node pipeline unchanged —
    it already *is* the final action. The rest are one-node graphs; the
    remaining three land in Phase 3.
    """
    match action_type:
        case ActionType.GENERATE_REVIEW:
            return build_analysis_graph(mode=mode)
        case ActionType.PROPOSE_TOPIC:
            return _build_single_node_graph("propose_topic", propose_topic)
        case _:
            raise ValueError(f"No graph for action type: {action_type!r}")
