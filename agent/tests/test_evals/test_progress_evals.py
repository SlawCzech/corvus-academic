"""Tests for the progress eval: the cases load, the score says what it should."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage

from evals.progress import (
    JudgeReply,
    ProgressCase,
    llm_judge,
    load_cases,
    render_markdown,
    report_text,
    run_case,
    score,
)
from src.infrastructure.llm_factory import ModelCredentials

_KEY = ModelCredentials(provider="claude", api_key="k")


def _case() -> ProgressCase:
    return ProgressCase(
        id="case",
        description="",
        previous="Wersja 1",
        current="Wersja 2",
        context={"meeting_notes": ["Uzasadnić dobór próby."]},
        must_say=("It says one thing.",),
        must_not_say=("It says another.",),
    )


def _output() -> dict[str, Any]:
    return {
        "summary": "Praca poszła do przodu.",
        "changes": [
            {"area": "Metodologia", "change": "Dodano dobór.", "assessment": "progress"}
        ],
        "concerns": ["Brak opisu ankiety."],
        "next_steps": ["Opisać ankietę."],
    }


def test_every_case_loads_with_notes_and_both_versions() -> None:
    cases = load_cases()

    assert {c.id for c in cases} == {
        "notatka-tylko-wspomina",
        "prosba-niewykonana",
        "prosba-wykonana",
    }
    for case in cases:
        assert case.context["meeting_notes"]
        assert case.previous.strip() and case.current.strip()
        assert case.previous != case.current
        assert case.must_say or case.must_not_say


def test_an_unknown_case_is_an_error() -> None:
    with pytest.raises(ValueError, match="Unknown progress cases"):
        load_cases(["nie-ma"])


def test_the_judge_reads_everything_the_supervisor_would() -> None:
    text = report_text(_output())

    assert "Praca poszła do przodu." in text
    assert "Metodologia: Dodano dobór. (progress)" in text
    assert "Brak opisu ankiety." in text
    assert "Opisać ankietę." in text


def test_a_good_reading_passes() -> None:
    verdict = JudgeReply(must_say={"1": True}, must_not_say={"1": False})

    assert score(_case(), _output(), verdict, "m", 1.0).passed


def test_what_went_unsaid_and_what_was_said_both_fail() -> None:
    verdict = JudgeReply(must_say={"1": False}, must_not_say={"1": True})

    result = score(_case(), _output(), verdict, "m", 1.0)

    assert not result.passed
    assert result.problems == [
        "did not say: It says one thing.",
        "said: It says another.",
    ]


def test_the_judge_reads_a_model_reply() -> None:
    llm: Any = MagicMock()
    llm.invoke.return_value = AIMessage(
        content='{"must_say": {"1": true}, "must_not_say": {"1": false}}'
    )

    verdict = llm_judge(llm)(_case(), _output())

    assert verdict.must_say == {"1": True}


def test_the_graph_gets_both_versions_and_the_notes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph: Any = MagicMock()
    graph.invoke.return_value = {"output": _output(), "error": None}
    monkeypatch.setattr("evals.progress.build_action_graph", lambda _: graph)
    judge = MagicMock(return_value=JudgeReply(must_say={"1": True}))

    assert run_case(_case(), "m", judge, _KEY).passed

    context = graph.invoke.call_args.args[0]["context"]
    assert context["previous_text"] == "Wersja 1"
    assert context["current_text"] == "Wersja 2"
    assert context["meeting_notes"] == ["Uzasadnić dobór próby."]


def test_a_failed_run_is_reported_not_judged(monkeypatch: pytest.MonkeyPatch) -> None:
    graph: Any = MagicMock()
    graph.invoke.return_value = {"output": None, "error": "model down"}
    monkeypatch.setattr("evals.progress.build_action_graph", lambda _: graph)
    judge = MagicMock()

    result = run_case(_case(), "m", judge, _KEY)

    assert result.error == "model down"
    judge.assert_not_called()
    assert "model down" in render_markdown([result])
