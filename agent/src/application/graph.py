"""LangGraph analysis pipeline graph definition."""

# LangGraph's add_node/compile overloads reference CachePolicy[Unknown] internally,
# which makes every call site reportUnknownMemberType. All other project code is
# fully typed — this suppression is scoped to this file only.
# pyright: reportUnknownMemberType=false

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .nodes.methodology import analyze_methodology
from .nodes.requirements import check_requirements
from .nodes.review import generate_review
from .nodes.structure import analyze_structure
from .state import AnalysisState


def build_analysis_graph(
    mode: str = "full",
) -> CompiledStateGraph[AnalysisState, None, Any, Any]:
    """Build and compile the thesis analysis graph for the given mode.

    mode="full"        — structure → methodology → requirements → review
    mode="review_only" — review only (no intermediate finding nodes)
    """
    builder: StateGraph[AnalysisState, None, Any, Any] = StateGraph(AnalysisState)

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
