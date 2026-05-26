"""LangGraph analysis pipeline graph definition."""

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .nodes.methodology import analyze_methodology
from .nodes.requirements import check_requirements
from .nodes.review import generate_review
from .nodes.structure import analyze_structure
from .state import AnalysisState


def build_analysis_graph() -> CompiledStateGraph:
    """Build and compile the sequential thesis analysis graph."""
    builder: StateGraph = StateGraph(AnalysisState)

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
