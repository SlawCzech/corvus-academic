"""Tests for the analyze_structure node."""

from typing import Any
from unittest.mock import MagicMock, patch

import anthropic
import httpx
import pytest
from langchain_core.messages import AIMessage

from src.application.nodes.structure import analyze_structure
from src.application.state import ActionState
from src.domain.action import ActionErrorCode
from src.domain.analysis import Finding, FindingSeverity, FindingSource
from src.infrastructure.provider_errors import ProviderAccountError
from tests.factories import make_state

_VALID_RESPONSE = (
    '[{"section": "Introduction", "description": "Missing abstract",'
    ' "severity": "major", "suggestion": "Add an abstract section."}]'
)


def _make_state() -> ActionState:
    return make_state(
        context={
            "text": "Chapter 1: Introduction. Chapter 2: Methodology.",
            "guidelines": "The thesis must have at least five chapters.",
            "metadata": {
                "author": "Jan Kowalski",
                "title": "Test Thesis",
                "year": 2024,
                "field_of_study": "Computer Science",
            },
        }
    )


def test_analyze_structure_happy_path() -> None:
    """Node returns non-empty findings and no error on successful LLM call."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_VALID_RESPONSE)

    with patch("src.application.nodes.structure.get_llm", return_value=mock_llm):
        result = analyze_structure(_make_state())

    assert len(result["findings"]) > 0
    assert "node_errors" not in result


def test_analyze_structure_api_error() -> None:
    """Node sets error and preserves empty findings when LLM raises."""
    mock_llm: Any = MagicMock()
    mock_llm.invoke.side_effect = Exception("API timeout")

    with patch("src.application.nodes.structure.get_llm", return_value=mock_llm):
        result = analyze_structure(_make_state())

    # Reported for the review to carry, not as the action's own error.
    assert result == {"node_errors": ["structure: API timeout"]}


def test_analyze_structure_returns_only_its_own_findings() -> None:
    """Earlier findings stay out of the update — the state's reducer sums them.

    Handing the whole list back would double it: the branches run in
    parallel and LangGraph adds each update to what is already there.
    """
    earlier = Finding(
        section="Wstęp",
        description="earlier",
        severity=FindingSeverity.MINOR,
        suggestion="-",
    )
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_VALID_RESPONSE)

    with patch("src.application.nodes.structure.get_llm", return_value=mock_llm):
        state = _make_state()
        state["findings"] = [earlier]
        result = analyze_structure(state)

    assert earlier not in result["findings"]
    assert len(result["findings"]) == 1


def test_findings_are_tagged_as_structure() -> None:
    """Each finding names the analysis that raised it."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_VALID_RESPONSE)

    with patch("src.application.nodes.structure.get_llm", return_value=mock_llm):
        result = analyze_structure(_make_state())

    assert {f.source for f in result["findings"]} == {FindingSource.STRUCTURE}


def test_the_guidelines_stay_out_of_the_structure_prompt() -> None:
    """Required elements are `check_requirements`' call, not this node's.

    Given the same rubric, both nodes reported the same missing chapter.
    """
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="[]")

    with patch("src.application.nodes.structure.get_llm", return_value=mock_llm):
        analyze_structure(_make_state())

    messages: list[Any] = mock_llm.invoke.call_args.args[0]
    sent = "".join(str(m.content) for m in messages)
    assert "at least five chapters" not in sent
    assert "Chapter 1: Introduction" in sent


def test_a_dead_provider_account_ends_the_run() -> None:
    """No credits is not one branch's bad luck: every later call fails too."""
    request = httpx.Request("POST", "https://api.anthropic.test/v1/messages")
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = anthropic.BadRequestError(
        "Error code: 400",
        response=httpx.Response(400, request=request),
        body={
            "type": "error",
            "error": {
                "type": "invalid_request_error",
                "message": "Your credit balance is too low to access the API.",
            },
        },
    )

    with (
        patch("src.application.nodes.structure.get_llm", return_value=mock_llm),
        pytest.raises(ProviderAccountError) as raised,
    ):
        analyze_structure(_make_state())

    assert raised.value.code is ActionErrorCode.PROVIDER_NO_CREDITS
