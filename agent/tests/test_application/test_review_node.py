"""Tests for the generate_review node."""

import json
from typing import Any, cast
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage

from src.application.nodes.review import generate_review
from src.application.state import AnalysisState
from src.domain.analysis import Finding, FindingSeverity

_VALID_RESPONSE = json.dumps(
    {
        "scores": [
            {"criteria": "Structure", "points": 8, "max_points": 10},
            {"criteria": "Methodology", "points": 7, "max_points": 10},
            {"criteria": "Requirements", "points": 9, "max_points": 10},
            {"criteria": "Overall Quality", "points": 8, "max_points": 10},
        ],
        "summary": "The thesis is well-structured with minor issues in methodology.",
        "recommendation": "pass",
    }
)


def _make_state(with_critical: bool = False) -> AnalysisState:
    findings: list[Finding] = []
    if with_critical:
        findings = [
            Finding(
                section="Methodology",
                description="No research design",
                severity=FindingSeverity.CRITICAL,
                suggestion="Add a research design chapter.",
            )
        ]
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
            "text": "Chapter 1: Introduction. Chapter 2: Background.",
            "guidelines": "Thesis must conform to university standards.",
            "findings": findings,
            "scores": [],
            "review": None,
            "status": "analyzing",
            "error": None,
        },
    )


def test_generate_review_happy_path() -> None:
    """Node produces a Review, non-empty scores, and sets status to 'analyzed'."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_VALID_RESPONSE)

    with patch("src.application.nodes.review.get_llm", return_value=mock_llm):
        result = generate_review(_make_state())

    assert result["review"] is not None
    assert len(result["scores"]) == 4
    assert result["status"] == "analyzed"
    assert result["error"] is None


def test_generate_review_rejected_when_critical_findings() -> None:
    """Node sets status to 'rejected' when findings include CRITICAL ones."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_VALID_RESPONSE)

    with patch("src.application.nodes.review.get_llm", return_value=mock_llm):
        result = generate_review(_make_state(with_critical=True))

    assert result["status"] == "rejected"
    assert result["review"] is not None
    assert result["error"] is None


def test_generate_review_api_error() -> None:
    """Node sets error and leaves review/scores/status unchanged when LLM raises."""
    mock_llm: Any = MagicMock()
    mock_llm.invoke.side_effect = Exception("Model unavailable")

    with patch("src.application.nodes.review.get_llm", return_value=mock_llm):
        result = generate_review(_make_state())

    assert result["error"] is not None
    assert result["review"] is None
    assert result["scores"] == []


def test_generate_review_score_percentage() -> None:
    """Review total_percentage is computed correctly across scores."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_VALID_RESPONSE)

    with patch("src.application.nodes.review.get_llm", return_value=mock_llm):
        result = generate_review(_make_state())

    review = result["review"]
    assert review is not None
    # 8+7+9+8 = 32 out of 40 max → 80.0%
    assert review.total_percentage() == 80.0


def test_generate_review_recommendation_stored() -> None:
    """Review recommendation field matches what the LLM returned."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_VALID_RESPONSE)

    with patch("src.application.nodes.review.get_llm", return_value=mock_llm):
        result = generate_review(_make_state())

    assert result["review"] is not None
    assert result["review"].recommendation == "pass"
