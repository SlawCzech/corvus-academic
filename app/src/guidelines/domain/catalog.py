"""Domain model of the guideline catalog.

The distinction the whole context exists for: a *regulation* is what the
university wrote (the original file, kept for reference and download); a
*rubric* is Corvus's reading of it — the checklist the model is given, plus
the numeric thresholds code can check. A version carries both, and once
published it never changes: a review records the version it was judged
against, and that record must keep meaning the same thing.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class ThesisType(StrEnum):
    """Kind of thesis a guideline set applies to.

    The same vocabulary as `mentoring.domain.student.ThesisType`, declared
    here rather than imported so the catalog does not depend on mentoring; a
    test keeps the two identical.
    """

    BACHELOR = "bachelor"
    MASTER_ARTICLE = "master_article"


class VersionStatus(StrEnum):
    """Where a guideline version is in its life."""

    DRAFT = "draft"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"


class VersionNotEditableError(ValueError):
    """Raised when something tries to change a version that is not a draft."""


def _require_text(value: str, field_name: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be empty")
    return stripped


@dataclass(frozen=True)
class University:
    """A university whose requirements the catalog holds."""

    id: UUID
    name: str
    short_name: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _require_text(self.name, "name"))
        object.__setattr__(
            self, "short_name", _require_text(self.short_name, "short_name")
        )


@dataclass(frozen=True)
class GuidelineSet:
    """One university's requirements for one kind of thesis, across versions."""

    id: UUID
    university_id: UUID
    thesis_type: ThesisType
    name: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _require_text(self.name, "name"))


@dataclass(frozen=True)
class Thresholds:
    """The numeric requirements, as data code can check.

    Every field is optional: a regulation that sets no length limit has none.
    """

    min_sources: int | None = None
    min_foreign_sources: int | None = None
    min_body_chars: int | None = None
    max_body_chars: int | None = None

    def __post_init__(self) -> None:
        for name, value in self.to_dict().items():
            if value is not None and value < 0:
                raise ValueError(f"{name} must not be negative")
        if (
            self.min_sources is not None
            and self.min_foreign_sources is not None
            and self.min_foreign_sources > self.min_sources
        ):
            raise ValueError("min_foreign_sources must not exceed min_sources")
        if (
            self.min_body_chars is not None
            and self.max_body_chars is not None
            and self.min_body_chars > self.max_body_chars
        ):
            raise ValueError("min_body_chars must not exceed max_body_chars")

    def to_dict(self) -> dict[str, int | None]:
        return {
            "min_sources": self.min_sources,
            "min_foreign_sources": self.min_foreign_sources,
            "min_body_chars": self.min_body_chars,
            "max_body_chars": self.max_body_chars,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "Thresholds":
        data = data or {}
        return cls(
            min_sources=data.get("min_sources"),
            min_foreign_sources=data.get("min_foreign_sources"),
            min_body_chars=data.get("min_body_chars"),
            max_body_chars=data.get("max_body_chars"),
        )


@dataclass(frozen=True)
class SourceDocument:
    """The regulation a version was read from — reference, not prompt."""

    file_id: UUID | None
    filename: str
    sha256: str
    size: int


@dataclass
class GuidelineVersion:
    """One version of a guideline set. Editable as a draft, frozen once published."""

    id: UUID
    set_id: UUID
    version_no: int
    created_by: UUID
    rubric_md: str = ""
    thresholds: Thresholds = field(default_factory=Thresholds)
    effective_from: date | None = None
    source: SourceDocument | None = None
    status: VersionStatus = VersionStatus.DRAFT
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    published_by: UUID | None = None
    published_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.version_no < 1:
            raise ValueError("version_no must start at 1")

    @property
    def is_draft(self) -> bool:
        return self.status is VersionStatus.DRAFT

    def edit(
        self,
        rubric_md: str | None = None,
        thresholds: Thresholds | None = None,
        effective_from: date | None = None,
    ) -> None:
        """Change a draft. Omitted fields are left as they are."""
        self._require_draft()
        if rubric_md is not None:
            self.rubric_md = rubric_md
        if thresholds is not None:
            self.thresholds = thresholds
        if effective_from is not None:
            self.effective_from = effective_from

    def attach_source(self, source: SourceDocument) -> None:
        """Record the regulation this draft was read from."""
        self._require_draft()
        self.source = source

    def publish(self, by: UUID, at: datetime | None = None) -> None:
        """Freeze the draft and make it the version actions are judged against."""
        self._require_draft()
        if not self.rubric_md.strip():
            raise ValueError("A version cannot be published without a rubric")
        self.status = VersionStatus.PUBLISHED
        self.published_by = by
        self.published_at = at or datetime.now(UTC)

    def supersede(self) -> None:
        """Step aside for a newer published version. Only a published one can."""
        if self.status is not VersionStatus.PUBLISHED:
            raise VersionNotEditableError(
                f"Only a published version can be superseded (is {self.status})"
            )
        self.status = VersionStatus.SUPERSEDED

    def _require_draft(self) -> None:
        if not self.is_draft:
            raise VersionNotEditableError(
                f"Version {self.version_no} is {self.status}; publish a new version "
                "instead of changing this one"
            )
