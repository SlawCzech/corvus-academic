"""Tests for the LangGraph action graphs."""

from collections.abc import Callable
from typing import cast
from unittest.mock import patch

import pytest

from src.application.graph import build_action_graph, build_analysis_graph
from src.application.state import ActionState
from src.domain.action import ActionType
from tests.factories import make_state


def _make_state() -> ActionState:
    return make_state(
        context={
            "text": "Chapter 1: Introduction.",
            "guidelines": "At least five chapters required.",
            "metadata": {
                "author": "Jan Kowalski",
                "title": "Test Thesis",
                "year": 2024,
                "field_of_study": "Computer Science",
            },
        }
    )


def _passthrough(state: ActionState) -> ActionState:
    """Typed stand-in for node mocks that must return state unchanged."""
    return state


def test_all_nodes_called() -> None:
    """Each of the four nodes is invoked exactly once when the graph runs."""
    with (
        patch(
            "src.application.graph.analyze_structure", side_effect=_passthrough
        ) as m1,
        patch(
            "src.application.graph.analyze_methodology", side_effect=_passthrough
        ) as m2,
        patch(
            "src.application.graph.check_requirements", side_effect=_passthrough
        ) as m3,
        patch("src.application.graph.generate_review", side_effect=_passthrough) as m4,
    ):
        graph = build_analysis_graph()
        graph.invoke(_make_state())  # pyright: ignore[reportUnknownMemberType]

    m1.assert_called_once()
    m2.assert_called_once()
    m3.assert_called_once()
    m4.assert_called_once()


def test_node_order() -> None:
    """Nodes execute in the correct sequential order."""
    call_log: list[str] = []

    def make_side_effect(name: str) -> Callable[[ActionState], ActionState]:
        def _fn(state: ActionState) -> ActionState:
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
        graph.invoke(_make_state())  # pyright: ignore[reportUnknownMemberType]

    assert call_log == [
        "analyze_structure",
        "analyze_methodology",
        "check_requirements",
        "generate_review",
    ]


def test_return_shape() -> None:
    """Graph result carries the whole ActionState through."""
    with (
        patch("src.application.graph.analyze_structure", side_effect=_passthrough),
        patch("src.application.graph.analyze_methodology", side_effect=_passthrough),
        patch("src.application.graph.check_requirements", side_effect=_passthrough),
        patch("src.application.graph.generate_review", side_effect=_passthrough),
    ):
        graph = build_analysis_graph()
        # Command[Unknown] in invoke() overloads is a LangGraph internal issue
        result = graph.invoke(_make_state())  # pyright: ignore[reportUnknownMemberType]

    required_keys = {
        "action_id",
        "action_type",
        "student_id",
        "context",
        "findings",
        "scores",
        "output",
        "status",
        "error",
    }
    assert required_keys.issubset(result.keys())


def test_no_short_circuit_on_error() -> None:
    """All downstream nodes still run even when analyze_structure sets an error."""
    call_log: list[str] = []

    def structure_with_error(state: ActionState) -> ActionState:
        result = dict(state)
        result["error"] = "boom"
        return cast(ActionState, result)

    def make_side_effect(name: str) -> Callable[[ActionState], ActionState]:
        def _fn(state: ActionState) -> ActionState:
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
        # Command[Unknown] in invoke() overloads is a LangGraph internal issue
        result = graph.invoke(_make_state())  # pyright: ignore[reportUnknownMemberType]

    assert result["error"] == "boom"
    assert call_log == ["analyze_methodology", "check_requirements", "generate_review"]


# ---------- action dispatch ----------


def test_review_action_reuses_the_full_pipeline() -> None:
    """generate_review already is the final action — no second graph for it."""
    call_log: list[str] = []

    def _log(name: str) -> Callable[[ActionState], ActionState]:
        def _fn(state: ActionState) -> ActionState:
            call_log.append(name)
            return state

        return _fn

    with (
        patch("src.application.graph.analyze_structure", side_effect=_log("structure")),
        patch(
            "src.application.graph.analyze_methodology", side_effect=_log("methodology")
        ),
        patch(
            "src.application.graph.check_requirements", side_effect=_log("requirements")
        ),
        patch("src.application.graph.generate_review", side_effect=_log("review")),
    ):
        graph = build_action_graph(ActionType.GENERATE_REVIEW)
        graph.invoke(_make_state())  # pyright: ignore[reportUnknownMemberType]

    assert call_log == ["structure", "methodology", "requirements", "review"]


def test_propose_topic_is_a_single_node_graph() -> None:
    """The other four nodes have nothing to do with proposing a topic."""
    call_log: list[str] = []

    def _log(name: str) -> Callable[[ActionState], ActionState]:
        def _fn(state: ActionState) -> ActionState:
            call_log.append(name)
            return state

        return _fn

    with (
        patch("src.application.graph.analyze_structure", side_effect=_log("structure")),
        patch("src.application.graph.generate_review", side_effect=_log("review")),
        patch("src.application.graph.propose_topic", side_effect=_log("propose_topic")),
    ):
        graph = build_action_graph(ActionType.PROPOSE_TOPIC)
        graph.invoke(_make_state(), )  # pyright: ignore[reportUnknownMemberType]

    assert call_log == ["propose_topic"]


def test_every_action_type_has_a_graph() -> None:
    """The catalog and the dispatcher must not drift apart."""
    for action_type in ActionType:
        assert build_action_graph(action_type) is not None


def test_unknown_action_is_rejected() -> None:
    """Anything outside the catalog is a programming error, said loudly."""
    with pytest.raises(ValueError, match="write_the_whole_thesis"):
        build_action_graph("write_the_whole_thesis")
