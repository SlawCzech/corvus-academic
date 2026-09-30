"""LangGraph graph definitions — one builder per action type."""

# LangGraph's add_node/compile overloads reference CachePolicy[Unknown] internally,
# which makes every call site reportUnknownMemberType. All other project code is
# fully typed — this suppression is scoped to this file only.
# pyright: reportUnknownMemberType=false

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.domain.action import ActionType

from .nodes.check_progress import check_progress
from .nodes.defence_questions import defence_questions
from .nodes.draft_meeting_note import draft_meeting_note
from .nodes.methodology import analyze_methodology
from .nodes.propose_topic import propose_topic
from .nodes.requirements import check_requirements
from .nodes.review import generate_review
from .nodes.structure import analyze_structure
from .nodes.verify import verify
from .state import ActionState

CompiledActionGraph = CompiledStateGraph[ActionState, None, Any, Any]

# Every action the agent can run. The API checks against this before queueing
# anything, so an unknown action type fails at the request, not in a worker.
IMPLEMENTED_ACTIONS: frozenset[str] = frozenset(ActionType)


def build_analysis_graph(mode: str = "full") -> CompiledActionGraph:
    """Build and compile the full thesis analysis graph for the given mode.

    mode="full"        — structure, methodology and requirements in parallel,
                         then `verify` once all three are done, then review
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
        builder.add_node("verify", verify)
        builder.add_node("generate_review", generate_review)
        analysis = ["analyze_structure", "analyze_methodology", "check_requirements"]
        for node in analysis:
            builder.add_edge(START, node)
        # A list as the source makes this a join: `verify` runs once, after
        # every branch has written its findings (or its error) to state —
        # the first point where they can be checked against each other.
        builder.add_edge(analysis, "verify")
        builder.add_edge("verify", "generate_review")
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


def _build_checked_analysis_graph(
    name: str, node: Any  # noqa: ANN401  — LangGraph node callables are untyped
) -> CompiledActionGraph:
    """One analysis node, its findings verified before they are returned."""
    builder: StateGraph[ActionState, None, Any, Any] = StateGraph(ActionState)
    builder.add_node(name, node)
    builder.add_node("verify", verify)
    builder.add_edge(START, name)
    builder.add_edge(name, "verify")
    builder.add_edge("verify", END)
    return builder.compile()


def build_action_graph(
    action_type: str, mode: str = "full"
) -> CompiledActionGraph:
    """Return the compiled graph that runs the given action.

    `generate_review` delegates to the four-node pipeline unchanged — it
    already *is* the final action. Every other action is one node: that is the
    point of the shared state, and it is why adding an action means adding a
    node and a prompt rather than a pipeline.
    """
    match action_type:
        case ActionType.GENERATE_REVIEW:
            return build_analysis_graph(mode=mode)
        case ActionType.PROPOSE_TOPIC:
            return _build_single_node_graph("propose_topic", propose_topic)
        case ActionType.EVALUATE_METHODOLOGY:
            # The same node the full review runs, checked the same way.
            return _build_checked_analysis_graph(
                "analyze_methodology", analyze_methodology
            )
        case ActionType.CHECK_PROGRESS:
            return _build_single_node_graph("check_progress", check_progress)
        case ActionType.DRAFT_MEETING_NOTE:
            return _build_single_node_graph(
                "draft_meeting_note", draft_meeting_note
            )
        case ActionType.DEFENCE_QUESTIONS:
            return _build_single_node_graph(
                "defence_questions", defence_questions
            )
        case _:
            raise ValueError(f"No graph for action type: {action_type!r}")
