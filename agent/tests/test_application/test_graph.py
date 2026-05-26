"""Tests for the LangGraph analysis pipeline graph."""

from collections.abc import Callable
from typing import cast
from unittest.mock import patch

from src.application.graph import build_analysis_graph
from src.application.state import AnalysisState


def _make_state() -> AnalysisState:
    return cast(
        AnalysisState,
        {
            "evaluation_id": "550e8400-e29b-41d4-a716-446655440000",
            "metadata": {
                "author": "Jan Kowalski",
                "title": "Test Thesis",
                "year": 2024,
                "field_of_study": "Computer Science",
            },
            "text": "Chapter 1: Introduction.",
            "guidelines": "At least five chapters required.",
            "findings": [],
            "scores": [],
            "review": None,
            "status": "uploaded",
            "error": None,
        },
    )


def test_all_nodes_called() -> None:
    """Each of the four nodes is invoked exactly once when the graph runs."""
    with (
        patch("src.application.graph.analyze_structure", side_effect=lambda s: s) as m1,
        patch(
            "src.application.graph.analyze_methodology", side_effect=lambda s: s
        ) as m2,
        patch(
            "src.application.graph.check_requirements", side_effect=lambda s: s
        ) as m3,
        patch("src.application.graph.generate_review", side_effect=lambda s: s) as m4,
    ):
        graph = build_analysis_graph()
        graph.invoke(_make_state())

    m1.assert_called_once()
    m2.assert_called_once()
    m3.assert_called_once()
    m4.assert_called_once()


def test_node_order() -> None:
    """Nodes execute in the correct sequential order."""
    call_log: list[str] = []

    def make_side_effect(name: str) -> Callable[[AnalysisState], AnalysisState]:
        def _fn(state: AnalysisState) -> AnalysisState:
            call_log.append(name)
            return state

        return _fn

    with (
        patch(
            "src.application.graph.analyze_structure",
            side_effect=make_side_effect("analyze_structure"),
        ),
        patch(
            "src.application.graph.analyze_methodology",
            side_effect=make_side_effect("analyze_methodology"),
        ),
        patch(
            "src.application.graph.check_requirements",
            side_effect=make_side_effect("check_requirements"),
        ),
        patch(
            "src.application.graph.generate_review",
            side_effect=make_side_effect("generate_review"),
        ),
    ):
        graph = build_analysis_graph()
        graph.invoke(_make_state())

    assert call_log == [
        "analyze_structure",
        "analyze_methodology",
        "check_requirements",
        "generate_review",
    ]


def test_return_shape() -> None:
    """Graph result contains all nine required AnalysisState keys."""
    with (
        patch("src.application.graph.analyze_structure", side_effect=lambda s: s),
        patch("src.application.graph.analyze_methodology", side_effect=lambda s: s),
        patch("src.application.graph.check_requirements", side_effect=lambda s: s),
        patch("src.application.graph.generate_review", side_effect=lambda s: s),
    ):
        graph = build_analysis_graph()
        result = graph.invoke(_make_state())

    required_keys = {
        "evaluation_id",
        "metadata",
        "text",
        "guidelines",
        "findings",
        "scores",
        "review",
        "status",
        "error",
    }
    assert required_keys.issubset(result.keys())


def test_no_short_circuit_on_error() -> None:
    """All downstream nodes still run even when analyze_structure sets an error."""
    call_log: list[str] = []

    def structure_with_error(state: AnalysisState) -> AnalysisState:
        result = dict(state)
        result["error"] = "boom"
        return cast(AnalysisState, result)

    def make_side_effect(name: str) -> Callable[[AnalysisState], AnalysisState]:
        def _fn(state: AnalysisState) -> AnalysisState:
            call_log.append(name)
            return state

        return _fn

    with (
        patch(
            "src.application.graph.analyze_structure",
            side_effect=structure_with_error,
        ),
        patch(
            "src.application.graph.analyze_methodology",
            side_effect=make_side_effect("analyze_methodology"),
        ),
        patch(
            "src.application.graph.check_requirements",
            side_effect=make_side_effect("check_requirements"),
        ),
        patch(
            "src.application.graph.generate_review",
            side_effect=make_side_effect("generate_review"),
        ),
    ):
        graph = build_analysis_graph()
        result = graph.invoke(_make_state())

    assert result["error"] == "boom"
    assert call_log == ["analyze_methodology", "check_requirements", "generate_review"]
