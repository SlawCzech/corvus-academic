"""Tests for the LangGraph action graphs."""

import threading
from collections.abc import Callable
from contextlib import ExitStack
from typing import Any
from unittest.mock import patch

import pytest

from src.application.graph import build_action_graph, build_analysis_graph
from src.application.state import ActionState, AnalysisUpdate, ReviewUpdate
from src.domain.action import ActionType
from src.domain.analysis import Finding, FindingSeverity
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


def _finding(section: str) -> Finding:
    return Finding(
        section=section,
        description=f"{section} issue",
        severity=FindingSeverity.MINOR,
        suggestion="fix it",
    )


def _branch(
    name: str, log: list[str] | None = None
) -> Callable[[ActionState], AnalysisUpdate]:
    """An analysis node that reports one finding named after itself."""

    def _fn(state: ActionState) -> AnalysisUpdate:
        if log is not None:
            log.append(name)
        return {"findings": [_finding(name)]}

    return _fn


def _failing(name: str) -> Callable[[ActionState], AnalysisUpdate]:
    def _fn(state: ActionState) -> AnalysisUpdate:
        return {"node_errors": [f"{name}: boom"]}

    return _fn


class _Review:
    """Records what the review node saw once the branches joined."""

    def __init__(self, log: list[str] | None = None) -> None:
        self.calls = 0
        self.seen_findings: list[str] = []
        self._log = log

    def __call__(self, state: ActionState) -> ReviewUpdate:
        self.calls += 1
        if self._log is not None:
            self._log.append("review")
        self.seen_findings = sorted(f.section for f in state["findings"])
        return {"output": {"summary": "ok"}, "status": "analyzed"}


def _patched(
    structure: Callable[[ActionState], AnalysisUpdate],
    methodology: Callable[[ActionState], AnalysisUpdate],
    requirements: Callable[[ActionState], AnalysisUpdate],
    review: Callable[[ActionState], ReviewUpdate],
) -> ExitStack:
    stack = ExitStack()
    stack.enter_context(
        patch("src.application.graph.analyze_structure", side_effect=structure)
    )
    stack.enter_context(
        patch("src.application.graph.analyze_methodology", side_effect=methodology)
    )
    stack.enter_context(
        patch("src.application.graph.check_requirements", side_effect=requirements)
    )
    stack.enter_context(
        patch("src.application.graph.generate_review", side_effect=review)
    )
    return stack


def _run(**nodes: Callable[[ActionState], Any]) -> dict[str, Any]:
    review = nodes.get("review", _Review())
    with _patched(
        nodes.get("structure", _branch("structure")),
        nodes.get("methodology", _branch("methodology")),
        nodes.get("requirements", _branch("requirements")),
        review,
    ):
        graph = build_analysis_graph()
        return dict(graph.invoke(_make_state()))  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]


def test_review_runs_once_after_all_three_branches() -> None:
    log: list[str] = []
    review = _Review(log)

    _run(
        structure=_branch("structure", log),
        methodology=_branch("methodology", log),
        requirements=_branch("requirements", log),
        review=review,
    )

    assert review.calls == 1
    assert log[-1] == "review"
    assert sorted(log[:-1]) == ["methodology", "requirements", "structure"]


def test_branches_really_run_at_the_same_time() -> None:
    """Each branch waits for the other two; run one by one, this would time out."""
    barrier = threading.Barrier(3, timeout=5)

    def _meet(name: str) -> Callable[[ActionState], AnalysisUpdate]:
        def _fn(state: ActionState) -> AnalysisUpdate:
            barrier.wait()
            return {"findings": [_finding(name)]}

        return _fn

    result = _run(
        structure=_meet("structure"),
        methodology=_meet("methodology"),
        requirements=_meet("requirements"),
    )

    assert len(result["findings"]) == 3


def test_every_branchs_findings_reach_the_review_once() -> None:
    review = _Review()

    result = _run(review=review)

    assert review.seen_findings == ["methodology", "requirements", "structure"]
    # Summed exactly once — not doubled by the review handing them back.
    assert len(result["findings"]) == 3


def test_a_failed_branch_is_kept_not_erased_by_the_others() -> None:
    review = _Review()

    result = _run(structure=_failing("structure"), review=review)

    assert result["node_errors"] == ["structure: boom"]
    assert result["error"] is None
    assert review.calls == 1  # the review still gets written
    assert review.seen_findings == ["methodology", "requirements"]


def test_two_branches_failing_in_the_same_step_are_both_kept() -> None:
    result = _run(
        structure=_failing("structure"), requirements=_failing("requirements")
    )

    assert sorted(result["node_errors"]) == ["requirements: boom", "structure: boom"]


def test_return_shape() -> None:
    """Graph result carries the whole ActionState through."""
    result = _run()

    required_keys = {
        "action_id",
        "action_type",
        "student_id",
        "context",
        "findings",
        "node_errors",
        "scores",
        "output",
        "status",
        "error",
    }
    assert required_keys.issubset(result.keys())


# ---------- action dispatch ----------


def test_review_action_reuses_the_full_pipeline() -> None:
    """generate_review already is the final action — no second graph for it."""
    log: list[str] = []
    with _patched(
        _branch("structure", log),
        _branch("methodology", log),
        _branch("requirements", log),
        _Review(log),
    ):
        graph = build_action_graph(ActionType.GENERATE_REVIEW)
        graph.invoke(_make_state())  # pyright: ignore[reportUnknownMemberType]

    assert sorted(log) == ["methodology", "requirements", "review", "structure"]
    assert log[-1] == "review"


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
        graph.invoke(
            _make_state(),
        )  # pyright: ignore[reportUnknownMemberType]

    assert call_log == ["propose_topic"]


def test_every_action_type_has_a_graph() -> None:
    """The catalog and the dispatcher must not drift apart."""
    for action_type in ActionType:
        assert build_action_graph(action_type) is not None


def test_unknown_action_is_rejected() -> None:
    """Anything outside the catalog is a programming error, said loudly."""
    with pytest.raises(ValueError, match="write_the_whole_thesis"):
        build_action_graph("write_the_whole_thesis")
