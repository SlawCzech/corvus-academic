"""Tests for the draft_rubric eval: its cases and checks, without a model."""

from typing import Any

from evals.rubric import CASES, JudgeReply, context_for, plain_checks, score


def _good(case_id: str = "bachelor") -> dict[str, Any]:
    case = CASES[case_id]
    return {
        **case.key(),
        "thresholds": dict(case.thresholds),
        "doubts": [],
    }


def test_the_regulations_read_from_the_seeded_files() -> None:
    text = CASES["bachelor"].regulation()

    assert "co najmniej 25 pozycji literaturowych" in text
    assert "Sugerowana objętość" in text


def test_each_draft_gets_the_other_sets_rubric_as_a_model() -> None:
    context = context_for(CASES["bachelor"])

    assert context["thesis_type"] == "bachelor"
    assert "Abstrakt" in context["example_rubric"]  # the master's rubric


def test_the_hand_written_rubric_passes_its_own_checks() -> None:
    for case_id, case in CASES.items():
        assert plain_checks(case, _good(case_id)) == [], case_id


def test_wrong_numbers_and_numbers_in_the_text_are_caught() -> None:
    case = CASES["bachelor"]
    draft = _good()
    draft["thresholds"] = {**draft["thresholds"], "min_sources": 20}
    draft["formal"] += "\n- co najmniej 25 pozycji\n- 80 000 – 130 000 znaków"

    problems = plain_checks(case, draft)

    assert "threshold min_sources: 20 (want 25)" in problems
    assert any("'25 pozycj'" in p for p in problems)
    assert any("80 000" in p for p in problems)


def test_a_heading_that_breaks_the_sections_is_caught() -> None:
    draft = _good()
    draft["merit"] = "## Inne\n- coś"

    assert "merit: a # or ## heading would break the sections" in plain_checks(
        CASES["bachelor"], draft
    )


def test_a_draft_passes_only_without_inventions_and_with_few_gaps() -> None:
    case = CASES["bachelor"]
    clean = score(case, _good(), JudgeReply(missing=["a"]), "claude", 1.0)
    invented = score(case, _good(), JudgeReply(invented=["x"]), "claude", 1.0)
    both = score(case, _good(), JudgeReply(both_required=True), "claude", 1.0)

    assert clean.passed
    assert not invented.passed
    assert not both.passed
