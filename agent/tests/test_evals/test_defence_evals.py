"""Tests for the defence eval: the checks catch the questions it exists to catch."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage

from evals.dataset import load_cases
from evals.defence import (
    JudgeReply,
    QuestionVerdict,
    llm_judge,
    plain_checks,
    questions_of,
    render_markdown,
    run_case,
    score,
)
from src.infrastructure.llm_factory import ModelCredentials

_KEY = ModelCredentials(provider="claude", api_key="k")

_GOOD = [
    "Co było celem pracy o motywowaniu pokolenia Z?",
    "Dlaczego ankieta była dobrą metodą w tym badaniu?",
    "Czy wnioski o małych firmach wynikają z wyników?",
]


def _output(*questions: str) -> dict[str, Any]:
    return {"questions": [{"question": q} for q in questions or _GOOD]}


def _verdict(**fields: Any) -> JudgeReply:  # noqa: ANN401
    aspects = ("aim", "method", "conclusions")
    return JudgeReply(
        questions={
            str(i): QuestionVerdict(
                **({"spoken": True, "this_thesis": True, "aspect": a} | fields)
            )
            for i, a in enumerate(aspects, 1)
        }
    )


def test_plain_checks_pass_three_short_questions() -> None:
    assert plain_checks(_output()) == []


def test_plain_checks_count_the_questions() -> None:
    assert plain_checks(_output(_GOOD[0])) == ["1 questions"]


def test_plain_checks_catch_a_paragraph_of_questions() -> None:
    long = " ".join(["słowo"] * 30) + "? I co dalej?"

    problems = plain_checks(_output(long, *_GOOD[1:]))

    assert "question 1: 33 words" in problems
    assert "question 1: not one question" in problems


def test_plain_checks_catch_two_questions_joined_by_and() -> None:
    problems = plain_checks(
        _output("Dlaczego ankieta i jakie ma ograniczenia?", *_GOOD[1:])
    )

    assert problems == ["question 1: not one question"]


def test_plain_checks_catch_figures_and_places() -> None:
    problems = plain_checks(
        _output("Skąd R² równe 0,21?", "Co pokazuje tabela o dochodach?", _GOOD[2])
    )

    assert "question 1: points at a detail (0)" in problems
    assert "question 2: points at a detail (tabela)" in problems


def test_questions_tolerate_the_older_shape() -> None:
    old = {"questions": [{"question": "Po co?", "rationale": "r", "focus": "problem"}]}

    assert questions_of(old) == ["Po co?"]


def test_score_reads_the_judge() -> None:
    case = load_cases(["pokolenie-z"])[0]

    clean = score(case, _output(), _verdict(), "m", 1.0)
    unspoken = score(case, _output(), _verdict(spoken=False), "m", 1.0)
    generic = score(case, _output(), _verdict(this_thesis=False), "m", 1.0)

    assert clean.passed
    assert "question 2: not answerable aloud" in unspoken.problems
    assert "question 3: fits any thesis" in generic.problems


def test_score_wants_all_three_aspects() -> None:
    case = load_cases(["pokolenie-z"])[0]

    result = score(case, _output(), _verdict(aspect="aim"), "m", 1.0)

    assert "nothing on: conclusions, method" in result.problems


def test_llm_judge_sees_the_title_and_the_numbered_questions() -> None:
    llm = MagicMock()
    llm.invoke.return_value = AIMessage(content='{"questions": {}}')
    case = load_cases(["pokolenie-z"])[0]

    llm_judge(llm)(case, _output())

    message = str(llm.invoke.call_args.args[0][1].content)
    assert str(case.metadata["title"]) in message
    assert f"1. {_GOOD[0]}" in message


def test_run_case_goes_through_the_real_graph() -> None:
    case = load_cases(["pokolenie-z"])[0]
    llm = MagicMock()
    llm.invoke.return_value = AIMessage(content=json.dumps(_output()))

    with patch("src.application.nodes.defence_questions.get_llm", return_value=llm):
        result = run_case(case, "m", lambda _c, _o: _verdict(), _KEY)

    assert result.passed, result.problems
    assert _GOOD[0] in render_markdown([result])
