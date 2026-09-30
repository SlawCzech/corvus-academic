"""Tests for the eval harness: the dataset, the judge's parsing, the numbers."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage

from evals.dataset import (
    EvalCase,
    ExpectedIssue,
    condensed_guidelines,
    load_cases,
)
from evals.judge import Judgement, llm_judge, parse_judgement
from evals.metrics import render_markdown, score_case, summarise
from src.domain.analysis import Finding, FindingSeverity, FindingSource


def _case() -> EvalCase:
    return EvalCase(
        id="case",
        description="",
        thesis_type="bachelor",
        text="Wstęp. Zakończenie.",
        metadata={"review_tone": "auto"},
        expected=(
            ExpectedIssue("no-hypotheses", "no hypotheses", FindingSeverity.CRITICAL),
            ExpectedIssue("few-sources", "few sources", FindingSeverity.CRITICAL),
            ExpectedIssue("vague-survey", "vague survey", FindingSeverity.MAJOR),
        ),
        must_not_flag=("There are no conclusions.", "There is no contents page."),
        acceptable_recommendations=("Zwrócić do poprawy",),
    )


def _finding(severity: FindingSeverity, text: str = "x") -> Finding:
    return Finding(
        section="Wstęp",
        description=text,
        severity=severity,
        suggestion="-",
        source=FindingSource.STRUCTURE,
    )


def _score(findings: list[Finding], judgement: Judgement, **kw: Any) -> Any:  # noqa: ANN401
    defaults: dict[str, Any] = {
        "model": "m",
        "seconds": 1.0,
        "node_seconds": {},
        "node_errors": [],
        "error": None,
        "recommendation": "Zwrócić do poprawy",
    }
    defaults.update(kw)
    return score_case(_case(), findings, judgement, **defaults)


# ---------- dataset ----------


def test_every_shipped_case_loads_with_an_answer_key() -> None:
    cases = load_cases()

    assert {c.id for c in cases} >= {"kryptowaluty", "oszczednosci", "pokolenie-z"}
    for case in cases:
        assert case.expected, case.id
        assert case.acceptable_recommendations, case.id
        assert len(case.text) < 30000, "a case must fit in one node's excerpt"


def test_unknown_case_ids_are_an_error() -> None:
    with pytest.raises(ValueError, match="nope"):
        load_cases(["nope"])


def test_condensed_guidelines_scale_only_the_length_rule() -> None:
    text = condensed_guidelines("bachelor")

    assert "80,000" not in text
    assert "7,000 – 20,000 characters" in text
    # Everything else is the real document.
    assert "Minimum:** 25 bibliographic sources" in text


def test_case_context_skips_retrieval_with_its_own_guidelines() -> None:
    context = load_cases(["kryptowaluty"])[0].context()

    assert context["guidelines"] == condensed_guidelines("bachelor")
    assert context["metadata"]["title"].startswith("Wpływ kryptowalut")


# ---------- judge ----------


def test_parse_judgement_drops_unknown_ids_and_made_up_numbers() -> None:
    data = {
        "expected": {"no-hypotheses": [1, "2", 9, "x", 1], "invented": [1]},
        "false_claims": {"1": [2], "7": [1]},
    }

    judgement = parse_judgement(data, _case(), finding_count=3)

    assert judgement.expected == {
        "no-hypotheses": [1, 2],
        "few-sources": [],
        "vague-survey": [],
    }
    assert judgement.false_claims == {1: [2], 2: []}


def test_parse_judgement_tolerates_a_malformed_reply() -> None:
    judgement = parse_judgement({"expected": "nope"}, _case(), finding_count=2)

    assert all(v == [] for v in judgement.expected.values())


def test_llm_judge_sends_numbered_findings_and_parses_the_reply() -> None:
    llm = MagicMock()
    llm.invoke.return_value = AIMessage(
        content='```json\n{"expected": {"few-sources": [2]}, "false_claims": {}}\n```'
    )
    findings = [
        _finding(FindingSeverity.MINOR, "typo"),
        _finding(FindingSeverity.CRITICAL, "9 sources"),
    ]

    judgement = llm_judge(llm)(_case(), findings)

    prompt = llm.invoke.call_args.args[0][1].content
    assert "2. [critical] (structure) Wstęp: 9 sources" in prompt
    assert judgement.expected["few-sources"] == [2]


def test_llm_judge_skips_the_call_when_there_is_nothing_to_judge() -> None:
    llm = MagicMock()

    judgement = llm_judge(llm)(_case(), [])

    llm.invoke.assert_not_called()
    assert judgement.expected["no-hypotheses"] == []


# ---------- metrics ----------


def test_score_counts_matches_misses_and_duplicates() -> None:
    findings = [
        _finding(FindingSeverity.CRITICAL),
        _finding(FindingSeverity.CRITICAL),
        _finding(FindingSeverity.MINOR),
        _finding(FindingSeverity.MINOR),
    ]
    judgement = Judgement(
        # Two findings restate the same planted defect: one duplicate.
        expected={"no-hypotheses": [1, 2], "few-sources": [], "vague-survey": [3]},
        false_claims={1: [], 2: []},
    )

    result = _score(findings, judgement)

    assert result.matched == ["no-hypotheses", "vague-survey"]
    assert result.missed == ["few-sources"]
    assert round(result.recall, 3) == round(2 / 3, 3)
    assert result.duplicates == 1
    # MINOR for a MAJOR defect: found, and still wrong.
    assert result.underrated == ["vague-survey"]
    # Finding 4 is about nothing in the key.
    assert result.unmatched == 1


def test_score_reports_false_flags_by_their_claim() -> None:
    findings = [_finding(FindingSeverity.CRITICAL, "no conclusions")]
    judgement = Judgement(expected={}, false_claims={1: [1], 2: []})

    result = _score(findings, judgement)

    assert result.false_flags == ["There are no conclusions."]
    assert result.unmatched == 0


def test_score_checks_the_recommendation_against_the_case() -> None:
    judgement = Judgement()

    assert _score([], judgement).recommendation_ok is True
    wrong = _score([], judgement, recommendation="Dopuścić do obrony")
    assert wrong.recommendation_ok is False
    # A methodology-only run writes no recommendation; nothing to judge.
    assert _score([], judgement, recommendation=None).recommendation_ok is None


def test_summary_and_report_aggregate_across_cases() -> None:
    judgement = Judgement(
        expected={"no-hypotheses": [1], "few-sources": [], "vague-survey": []},
        false_claims={1: [], 2: []},
    )
    results = [
        _score([_finding(FindingSeverity.CRITICAL)], judgement, seconds=10.0),
        _score([], Judgement(), seconds=5.0, node_errors=["structure: bad json"]),
    ]

    summary = summarise(results)
    report = render_markdown(results)

    assert summary.recall == 0.17  # mean of 1/3 and 0, rounded
    assert summary.failed_nodes == 1
    assert summary.seconds == 15.0
    assert summary.recommendations_ok == "2/2"
    assert "| case | 0.33 |" in report
