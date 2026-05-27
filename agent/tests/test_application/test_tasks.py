"""Tests for the analyze_thesis Celery task."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from celery.exceptions import Retry

from src.application.tasks import analyze_thesis
from src.infrastructure.celery_app import celery_app

_EVALUATION_ID = "550e8400-e29b-41d4-a716-446655440000"
_TEXT = "Chapter 1: Introduction. Chapter 2: Methodology."
_GUIDELINES = "The thesis must have at least five chapters."
_METADATA: dict[str, Any] = {
    "author": "Jan Kowalski",
    "title": "Test Thesis",
    "year": 2024,
    "field_of_study": "Computer Science",
}


@pytest.fixture(autouse=True)
def _eager_mode() -> None:  # pyright: ignore[reportUnusedFunction]
    """Execute Celery tasks synchronously in tests."""
    celery_app.conf.update(task_always_eager=True, task_eager_propagates=True)


def _graph_result() -> dict[str, Any]:
    return {
        "evaluation_id": _EVALUATION_ID,
        "metadata": _METADATA,
        "text": _TEXT,
        "guidelines": _GUIDELINES,
        "findings": [],
        "scores": [],
        "review": None,
        "status": "analyzed",
        "error": None,
    }


def test_task_calls_graph_with_correct_state() -> None:
    """Task builds and passes a valid AnalysisState to the graph."""
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = _graph_result()

    with patch("src.application.tasks.build_analysis_graph", return_value=mock_graph):
        analyze_thesis.apply(args=(_EVALUATION_ID, _TEXT, _GUIDELINES, _METADATA))

    mock_graph.invoke.assert_called_once()
    call_state: dict[str, Any] = mock_graph.invoke.call_args[0][0]
    assert call_state["evaluation_id"] == _EVALUATION_ID
    assert call_state["text"] == _TEXT
    assert call_state["guidelines"] == _GUIDELINES
    assert call_state["findings"] == []
    assert call_state["status"] == "analyzing"
    assert call_state["error"] is None


def test_task_returns_graph_result() -> None:
    """Task returns the dict produced by the graph."""
    expected = _graph_result()
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = expected

    with patch("src.application.tasks.build_analysis_graph", return_value=mock_graph):
        result = analyze_thesis.apply(
            args=(_EVALUATION_ID, _TEXT, _GUIDELINES, _METADATA)
        )

    assert result.get() == expected


def test_task_retries_on_exception() -> None:
    """Task signals retry when the graph raises an exception."""
    with patch("src.application.tasks.build_analysis_graph") as mock_factory:
        mock_factory.side_effect = Exception("Graph failed")

        # In eager mode, self.retry() raises Retry rather than re-executing
        with pytest.raises(Retry):
            analyze_thesis.apply(
                args=(_EVALUATION_ID, _TEXT, _GUIDELINES, _METADATA),
                throw=True,
            )

    mock_factory.assert_called_once()
