"""Unit tests for the guideline catalog's domain rules."""

import re
import uuid
from pathlib import Path

import pytest

from src.guidelines.domain.catalog import (
    GuidelineVersion,
    SourceDocument,
    ThesisType,
    Thresholds,
    VersionNotEditableError,
    VersionStatus,
)
from src.guidelines.domain.rubric import RubricShapeError, parse_rubric
from src.mentoring.domain.student import ThesisType as MentoringThesisType
from tests.rubrics import rubric

_ADMIN = uuid.uuid4()


def _draft(rubric_md: str = rubric()) -> GuidelineVersion:
    return GuidelineVersion(
        id=uuid.uuid4(),
        set_id=uuid.uuid4(),
        version_no=1,
        created_by=_ADMIN,
        rubric_md=rubric_md,
    )


def test_thesis_types_match_mentoring() -> None:
    """Declared twice to keep the contexts apart — so they must not drift."""
    assert {t.value for t in ThesisType} == {t.value for t in MentoringThesisType}


def test_a_draft_can_be_edited_and_published() -> None:
    version = _draft()

    version.edit(rubric_md=rubric("v2"), thresholds=Thresholds(min_sources=25))
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
        _draft(rubric_md="   ").publish(by=_ADMIN)


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


def test_a_rubric_without_the_four_sections_cannot_be_published() -> None:
    with pytest.raises(RubricShapeError, match="missing sections: Waga uchybień"):
        _draft(rubric_md=rubric().split("## Waga uchybień")[0]).publish(by=_ADMIN)


def test_a_rubric_with_a_section_of_its_own_cannot_be_published() -> None:
    with pytest.raises(RubricShapeError, match="Unknown rubric section 'Inne'"):
        _draft(rubric_md=rubric() + "\n## Inne\nCoś.\n").publish(by=_ADMIN)


def test_a_rubric_splits_into_its_sections_without_the_title() -> None:
    sections = parse_rubric(rubric("v3"))

    assert sections.elements == "Wstęp z celem (v3)."
    assert sections.severity == "CRITICAL: brak wstępu (v3)."
    assert "Wymogi v3" not in "".join(sections.to_dict().values())


def test_an_empty_section_is_named() -> None:
    text = rubric().replace("Logiczny tok wywodu (v1).", "")

    with pytest.raises(RubricShapeError, match="empty: Co praca ma wykazać"):
        parse_rubric(text)


@pytest.mark.parametrize("name", ["bachelor.md", "master_article.md"])
def test_the_seeded_rubrics_have_the_four_sections(name: str) -> None:
    seed = Path(__file__).parents[2] / "scripts" / "seed_data" / "guidelines" / name

    sections = parse_rubric(seed.read_text("utf-8"))

    # The numbers live in the thresholds alone.
    assert not re.search(r"\b\d{2,3} ?000\b", "".join(sections.to_dict().values()))
