"""Tests for the promoter's pause, outside a graph."""

from unittest.mock import patch

from src.application.nodes.promoter_review import promoter_review
from src.domain.analysis import Finding, FindingSeverity
from tests.factories import make_state

_FINDINGS = [
    Finding("Wstęp", "a", FindingSeverity.CRITICAL, "-"),
    Finding("Wstęp", "b", FindingSeverity.MINOR, "-"),
]


def test_passes_through_when_the_promoter_did_not_ask() -> None:
    with patch("src.application.nodes.promoter_review.interrupt") as pause:
        assert promoter_review(make_state(findings=_FINDINGS)) == {}
    pause.assert_not_called()


def test_keeps_the_accepted_findings_in_their_order() -> None:
    state = make_state(context={"promoter_reviews_findings": True}, findings=_FINDINGS)
    with patch(
        "src.application.nodes.promoter_review.interrupt",
        return_value={"accepted": [1, 7, "x"]},
    ) as pause:
        update = promoter_review(state)

    assert pause.call_args.args[0] == {"finding_count": 2}
    assert update["findings"].value == [_FINDINGS[1]]


def test_a_decision_without_a_list_keeps_everything() -> None:
    state = make_state(context={"promoter_reviews_findings": True}, findings=_FINDINGS)
    with patch("src.application.nodes.promoter_review.interrupt", return_value="ok"):
        assert promoter_review(state) == {}
