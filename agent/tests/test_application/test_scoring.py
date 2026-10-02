"""The bands a review's scores are held to — decided by the findings."""

from src.application.scoring import score_bands, within_band
from src.domain.analysis import Finding, FindingSeverity, FindingSource


def _finding(severity: FindingSeverity, source: FindingSource | None) -> Finding:
    return Finding(
        section="s", description="d", severity=severity, suggestion="", source=source
    )


def test_a_thesis_without_findings_scores_eight_or_more_everywhere() -> None:
    assert score_bands([]) == [(8, 10)] * 4


def test_minor_findings_do_not_lower_a_band() -> None:
    findings = [_finding(FindingSeverity.MINOR, FindingSource.METHODOLOGY)] * 6
    assert score_bands(findings) == [(8, 10)] * 4


def test_a_major_finding_lowers_its_own_criterion_and_the_overall_one() -> None:
    findings = [_finding(FindingSeverity.MAJOR, FindingSource.REQUIREMENTS)]
    assert score_bands(findings) == [(8, 10), (8, 10), (7, 8), (7, 8)]


def test_structure_and_coherence_share_the_first_criterion() -> None:
    findings = [
        _finding(FindingSeverity.MAJOR, FindingSource.STRUCTURE),
        _finding(FindingSeverity.MAJOR, FindingSource.COHERENCE),
    ]
    assert score_bands(findings)[0] == (6, 7)


def test_the_overall_criterion_tolerates_three_major_findings() -> None:
    three = [
        _finding(FindingSeverity.MAJOR, FindingSource.COHERENCE),
        _finding(FindingSeverity.MAJOR, FindingSource.COHERENCE),
        _finding(FindingSeverity.MAJOR, FindingSource.REQUIREMENTS),
    ]
    assert score_bands(three) == [(6, 7), (8, 10), (7, 8), (7, 8)]
    four = [*three, _finding(FindingSeverity.MAJOR, FindingSource.METHODOLOGY)]
    assert score_bands(four)[3] == (6, 7)


def test_a_critical_finding_caps_its_criterion_and_the_overall_one_at_five() -> None:
    findings = [_finding(FindingSeverity.CRITICAL, FindingSource.METHODOLOGY)]
    assert score_bands(findings) == [(8, 10), (0, 5), (8, 10), (0, 5)]


def test_a_finding_without_a_source_counts_only_overall() -> None:
    findings = [_finding(FindingSeverity.MAJOR, None)]
    assert score_bands(findings) == [(8, 10), (8, 10), (8, 10), (7, 8)]


def test_an_extra_criterion_is_judged_like_the_overall_one() -> None:
    findings = [_finding(FindingSeverity.CRITICAL, FindingSource.STRUCTURE)]
    assert score_bands(findings, 5)[4] == (0, 5)


def test_points_are_moved_into_the_band_only_on_a_ten_point_scale() -> None:
    assert within_band(5, 10, (7, 8)) == 7
    assert within_band(10, 10, (7, 8)) == 8
    assert within_band(7, 10, (7, 8)) == 7
    assert within_band(3, 5, (7, 8)) == 3
