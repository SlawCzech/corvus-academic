"""Tests for the fragment eval: the cases load, the checks catch what they should."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage

from evals.fragments import (
    FragmentCase,
    JudgeReply,
    feedback_text,
    llm_judge,
    load_cases,
    plain_checks,
    render_markdown,
    run_case,
    score,
)
from src.domain.action import ActionType


def _case(**fields: Any) -> FragmentCase:  # noqa: ANN401
    values: dict[str, Any] = {
        "id": "case",
        "description": "",
        "text": "Rozdział.",
        "context": {},
        "acceptable_directions": ("on_track",),
        "must_say": ("It says one thing.",),
        "must_not_say": ("It says another.",),
    }
    return FragmentCase(**(values | fields))


def _output(**fields: Any) -> dict[str, Any]:  # noqa: ANN401
    output: dict[str, Any] = {
        "summary": "Fragment omawia teorię.",
        "answer": "",
        "direction": "on_track",
        "strengths": ["Jasna teza."],
        "changes": [],
        "additions": [],
        "addressed": [],
        "next_step": "Pisać dalej.",
    }
    return output | fields


def test_every_case_loads_and_says_what_it_expects() -> None:
    cases = load_cases()

    assert {c.id for c in cases} == {
        "poza-tematem",
        "runda-druga",
        "solidny-rozdzial",
        "urwany-rozdzial",
    }
    assert all(c.text.strip() for c in cases)
    assert all(c.acceptable_directions for c in cases)


def test_an_unknown_case_is_refused() -> None:
    with pytest.raises(ValueError, match="nope"):
        load_cases(["nope"])


def test_a_clean_output_passes_the_plain_checks() -> None:
    assert plain_checks(_case(), _output()) == []


def test_the_summary_is_not_what_the_student_reads() -> None:
    text = feedback_text(_output(summary="TYLKO DLA PROMOTORA"))

    assert "TYLKO DLA PROMOTORA" not in text
    assert "Jasna teza." in text


@pytest.mark.parametrize(
    ("output", "problem"),
    [
        (_output(direction="needs_changes"), "direction"),
        (_output(strengths=[]), "nothing named"),
        (_output(summary=" "), "no summary"),
        (_output(changes=[{"point": "x", "quote": ""}] * 4), "too many changes"),
        (_output(additions=["x"] * 4), "too many additions"),
        (_output(next_step="Ocena: 3 z tego rozdziału."), "grade"),
        (_output(next_step="Rozdział wart 4/5."), "grade"),
        (_output(next_step="To niedopuszczalne."), "harsh"),
    ],
)
def test_the_plain_checks_catch(output: dict[str, Any], problem: str) -> None:
    assert any(problem in p for p in plain_checks(_case(), output))


def test_the_score_counts_the_judges_reading() -> None:
    verdict = JudgeReply(
        encouraging=False, must_say={"1": False}, must_not_say={"1": True}
    )

    result = score(_case(), _output(), verdict, "m", 1.0)

    assert not result.passed
    assert "not encouraging" in result.problems
    assert "did not say: It says one thing." in result.problems
    assert "said: It says another." in result.problems


def test_a_good_reading_passes() -> None:
    verdict = JudgeReply(
        encouraging=True, must_say={"1": True}, must_not_say={"1": False}
    )

    assert score(_case(), _output(), verdict, "m", 1.0).passed


def test_the_judge_reads_a_model_reply() -> None:
    llm: Any = MagicMock()
    llm.invoke.return_value = AIMessage(
        content='{"encouraging": true, "must_say": {"1": true}, "must_not_say": {}}'
    )

    verdict = llm_judge(llm)(_case(), _output())

    assert verdict.encouraging
    assert verdict.must_say == {"1": True}


def test_a_failed_run_is_reported_not_judged(monkeypatch: pytest.MonkeyPatch) -> None:
    graph: Any = MagicMock()
    graph.invoke.return_value = {"output": None, "error": "model down"}
    monkeypatch.setattr("evals.fragments.build_action_graph", lambda _: graph)
    judge = MagicMock()

    result = run_case(_case(), "m", judge)

    assert result.error == "model down"
    judge.assert_not_called()
    assert "model down" in render_markdown([result])


def test_the_action_type_has_a_graph() -> None:
    assert ActionType.REVIEW_FRAGMENT == "review_fragment"
