"""Tests for all domain entities in agent/src/domain/."""

from uuid import UUID, uuid4

import pytest

from src.domain.analysis import Finding, FindingSeverity, ThesisAnalysis
from src.domain.evaluation import (
    VALID_TRANSITIONS,
    EvaluationStatus,
    ThesisEvaluation,
)
from src.domain.metadata import ThesisMetadata
from src.domain.review import Review, Score

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_metadata() -> ThesisMetadata:
    return ThesisMetadata(
        author="John Smith",
        title="ZUsing LLMs in education",
        year=2025,
        field_of_study="Computer Science",
    )


@pytest.fixture()
def thesis_id() -> UUID:
    return uuid4()


@pytest.fixture()
def review_id() -> UUID:
    return uuid4()


@pytest.fixture()
def critical_finding() -> Finding:
    return Finding(
        section="Introduction",
        description="Missing research question",
        severity=FindingSeverity.CRITICAL,
        suggestion="Add a clearly stated research question.",
    )


@pytest.fixture()
def minor_finding() -> Finding:
    return Finding(
        section="References",
        description="Inconsistent citation format",
        severity=FindingSeverity.MINOR,
        suggestion="Use APA 7th edition throughout.",
    )


# ---------------------------------------------------------------------------
# ThesisMetadata — frozen Value Object
# ---------------------------------------------------------------------------


def test_metadata_is_frozen(sample_metadata: ThesisMetadata) -> None:
    with pytest.raises(AttributeError):
        sample_metadata.author = "Other Autor"  # type: ignore[misc]


def test_metadata_equality() -> None:
    m1 = ThesisMetadata("A", "T", 2024, "IT")
    m2 = ThesisMetadata("A", "T", 2024, "IT")
    assert m1 == m2


# ---------------------------------------------------------------------------
# ThesisAnalysis
# ---------------------------------------------------------------------------


def test_critical_count_empty(thesis_id: UUID) -> None:
    analysis = ThesisAnalysis(thesis_id=thesis_id)
    assert analysis.critical_count() == 0


def test_critical_count(
    thesis_id: UUID,
    critical_finding: Finding,
    minor_finding: Finding,
) -> None:
    analysis = ThesisAnalysis(
        thesis_id=thesis_id,
        findings=[critical_finding, minor_finding],
    )
    assert analysis.critical_count() == 1


def test_is_ready_to_submit_no_criticals(
    thesis_id: UUID, minor_finding: Finding
) -> None:
    analysis = ThesisAnalysis(thesis_id=thesis_id, findings=[minor_finding])
    assert analysis.is_ready_to_submit() is True


def test_is_ready_to_submit_with_critical(
    thesis_id: UUID, critical_finding: Finding
) -> None:
    analysis = ThesisAnalysis(thesis_id=thesis_id, findings=[critical_finding])
    assert analysis.is_ready_to_submit() is False


# ---------------------------------------------------------------------------
# Score
# ---------------------------------------------------------------------------


def test_score_percentage_normal() -> None:
    score = Score(criteria="Structure", points=8, max_points=10)
    assert score.percentage() == pytest.approx(80.0)  # pyright: ignore[reportUnknownMemberType]


def test_score_percentage_zero_max() -> None:
    score = Score(criteria="Empty", points=0, max_points=0)
    assert score.percentage() == pytest.approx(0.0)  # pyright: ignore[reportUnknownMemberType]


def test_score_is_frozen() -> None:
    score = Score(criteria="X", points=5, max_points=10)
    with pytest.raises(AttributeError):
        score.points = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------


def test_review_total_percentage(thesis_id: UUID, review_id: UUID) -> None:
    scores = [
        Score("Structure", 8, 10),
        Score("Methodology", 15, 20),
    ]
    review = Review(
        review_id=review_id,
        thesis_id=thesis_id,
        scores=scores,
        summary="Good work.",
        recommendation="Accept",
    )
    # (8+15)/(10+20)*100 = 76.666...
    assert review.total_percentage() == pytest.approx(76.666, rel=1e-3)  # pyright: ignore[reportUnknownMemberType]


def test_review_total_percentage_zero_max(thesis_id: UUID, review_id: UUID) -> None:
    review = Review(
        review_id=review_id,
        thesis_id=thesis_id,
        scores=[Score("X", 0, 0)],
        summary="",
        recommendation="",
    )
    assert review.total_percentage() == pytest.approx(0.0)  # pyright: ignore[reportUnknownMemberType]


def test_review_is_frozen(thesis_id: UUID, review_id: UUID) -> None:
    review = Review(
        review_id=review_id,
        thesis_id=thesis_id,
        scores=[],
        summary="s",
        recommendation="r",
    )
    with pytest.raises(AttributeError):
        review.summary = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# EvaluationStatus — valid transitions
# ---------------------------------------------------------------------------


def test_all_valid_transitions_present() -> None:
    assert set(VALID_TRANSITIONS.keys()) == set(EvaluationStatus)


def test_start_analysis(thesis_id: UUID, sample_metadata: ThesisMetadata) -> None:
    ev = ThesisEvaluation(id=thesis_id, metadata=sample_metadata)
    ev.start_analysis()
    assert ev.status == EvaluationStatus.ANALYZING


def test_complete_analysis_analyzed(
    thesis_id: UUID, sample_metadata: ThesisMetadata, minor_finding: Finding
) -> None:
    ev = ThesisEvaluation(id=thesis_id, metadata=sample_metadata)
    ev.start_analysis()
    analysis = ThesisAnalysis(thesis_id=thesis_id, findings=[minor_finding])
    ev.complete_analysis(analysis)
    assert ev.status == EvaluationStatus.ANALYZED
    assert ev.analysis is analysis


def test_complete_analysis_rejected(
    thesis_id: UUID,
    sample_metadata: ThesisMetadata,
    critical_finding: Finding,
) -> None:
    ev = ThesisEvaluation(id=thesis_id, metadata=sample_metadata)
    ev.start_analysis()
    analysis = ThesisAnalysis(thesis_id=thesis_id, findings=[critical_finding])
    ev.complete_analysis(analysis)
    assert ev.status == EvaluationStatus.REJECTED


def test_attach_review(
    thesis_id: UUID,
    review_id: UUID,
    sample_metadata: ThesisMetadata,
    minor_finding: Finding,
) -> None:
    ev = ThesisEvaluation(id=thesis_id, metadata=sample_metadata)
    ev.start_analysis()
    ev.complete_analysis(ThesisAnalysis(thesis_id=thesis_id, findings=[minor_finding]))
    review = Review(
        review_id=review_id,
        thesis_id=thesis_id,
        scores=[],
        summary="OK",
        recommendation="Accept",
    )
    ev.attach_review(review)
    assert ev.status == EvaluationStatus.REVIEWED
    assert ev.review is review


# ---------------------------------------------------------------------------
# EvaluationStatus — invalid transitions
# ---------------------------------------------------------------------------


def test_invalid_transition_uploaded_to_analyzed(
    thesis_id: UUID, sample_metadata: ThesisMetadata
) -> None:
    ev = ThesisEvaluation(id=thesis_id, metadata=sample_metadata)
    with pytest.raises(ValueError, match="uploaded"):
        ev.complete_analysis(ThesisAnalysis(thesis_id=thesis_id))


def test_invalid_transition_reviewed_to_analyzing(
    thesis_id: UUID,
    review_id: UUID,
    sample_metadata: ThesisMetadata,
    minor_finding: Finding,
) -> None:
    ev = ThesisEvaluation(id=thesis_id, metadata=sample_metadata)
    ev.start_analysis()
    ev.complete_analysis(ThesisAnalysis(thesis_id=thesis_id, findings=[minor_finding]))
    ev.attach_review(
        Review(
            review_id=review_id,
            thesis_id=thesis_id,
            scores=[],
            summary="",
            recommendation="",
        )
    )
    with pytest.raises(ValueError, match="reviewed"):
        ev.start_analysis()


def test_invalid_transition_rejected_to_analyzing(
    thesis_id: UUID,
    sample_metadata: ThesisMetadata,
    critical_finding: Finding,
) -> None:
    ev = ThesisEvaluation(id=thesis_id, metadata=sample_metadata)
    ev.start_analysis()
    ev.complete_analysis(
        ThesisAnalysis(thesis_id=thesis_id, findings=[critical_finding])
    )
    with pytest.raises(ValueError, match="rejected"):
        ev.start_analysis()


# ---------------------------------------------------------------------------
# is_complete()
# ---------------------------------------------------------------------------


def test_is_complete_initial(thesis_id: UUID, sample_metadata: ThesisMetadata) -> None:
    ev = ThesisEvaluation(id=thesis_id, metadata=sample_metadata)
    assert ev.is_complete() is False


def test_is_complete_after_review(
    thesis_id: UUID,
    review_id: UUID,
    sample_metadata: ThesisMetadata,
    minor_finding: Finding,
) -> None:
    ev = ThesisEvaluation(id=thesis_id, metadata=sample_metadata)
    ev.start_analysis()
    ev.complete_analysis(ThesisAnalysis(thesis_id=thesis_id, findings=[minor_finding]))
    ev.attach_review(
        Review(
            review_id=review_id,
            thesis_id=thesis_id,
            scores=[],
            summary="",
            recommendation="",
        )
    )
    assert ev.is_complete() is True


def test_is_complete_after_rejection(
    thesis_id: UUID,
    sample_metadata: ThesisMetadata,
    critical_finding: Finding,
) -> None:
    ev = ThesisEvaluation(id=thesis_id, metadata=sample_metadata)
    ev.start_analysis()
    ev.complete_analysis(
        ThesisAnalysis(thesis_id=thesis_id, findings=[critical_finding])
    )
    assert ev.is_complete() is True
