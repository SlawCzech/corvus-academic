"""Unit tests for the guideline catalog's domain rules."""

import uuid

import pytest

from src.guidelines.domain.catalog import (
    GuidelineVersion,
    SourceDocument,
    ThesisType,
    Thresholds,
    VersionNotEditableError,
    VersionStatus,
)
from src.mentoring.domain.student import ThesisType as MentoringThesisType

_ADMIN = uuid.uuid4()


def _draft(rubric: str = "## 1. Structure") -> GuidelineVersion:
    return GuidelineVersion(
        id=uuid.uuid4(),
        set_id=uuid.uuid4(),
        version_no=1,
        created_by=_ADMIN,
        rubric_md=rubric,
    )


def test_thesis_types_match_mentoring() -> None:
    """Declared twice to keep the contexts apart — so they must not drift."""
    assert {t.value for t in ThesisType} == {t.value for t in MentoringThesisType}


def test_a_draft_can_be_edited_and_published() -> None:
    version = _draft()

    version.edit(rubric_md="## 1. New", thresholds=Thresholds(min_sources=25))
    version.publish(by=_ADMIN)

    assert version.status is VersionStatus.PUBLISHED
    assert version.published_by == _ADMIN
    assert version.published_at is not None
    assert version.thresholds.min_sources == 25


def test_a_published_version_refuses_every_change() -> None:
    version = _draft()
    version.publish(by=_ADMIN)

    with pytest.raises(VersionNotEditableError):
        version.edit(rubric_md="changed")
    with pytest.raises(VersionNotEditableError):
        version.attach_source(SourceDocument(uuid.uuid4(), "z.pdf", "ab", 1))
    with pytest.raises(VersionNotEditableError):
        version.publish(by=_ADMIN)


def test_an_empty_rubric_cannot_be_published() -> None:
    with pytest.raises(ValueError, match="without a rubric"):
        _draft(rubric="   ").publish(by=_ADMIN)


def test_only_a_published_version_can_be_superseded() -> None:
    version = _draft()
    with pytest.raises(VersionNotEditableError):
        version.supersede()

    version.publish(by=_ADMIN)
    version.supersede()

    assert version.status is VersionStatus.SUPERSEDED


@pytest.mark.parametrize(
    "fields",
    [
        {"min_sources": -1},
        {"min_sources": 10, "min_foreign_sources": 11},
        {"min_body_chars": 100, "max_body_chars": 99},
    ],
)
def test_inconsistent_thresholds_are_rejected(fields: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        Thresholds(**fields)


def test_thresholds_round_trip_through_a_dict() -> None:
    thresholds = Thresholds(min_sources=40, min_foreign_sources=8)

    assert Thresholds.from_dict(thresholds.to_dict()) == thresholds
    assert Thresholds.from_dict(None) == Thresholds()
