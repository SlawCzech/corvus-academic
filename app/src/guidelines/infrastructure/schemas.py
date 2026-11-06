"""Request and response models for the guideline catalog API."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from src.guidelines.application.catalog import SetDetail, SetSummary, VersionDetail
from src.guidelines.domain.catalog import (
    GuidelineVersion,
    ThesisType,
    Thresholds,
    University,
)

# ---------- requests ----------


class UniversityCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    short_name: str = Field(min_length=1, max_length=50)


class SetCreateRequest(BaseModel):
    university_id: uuid.UUID
    thesis_type: ThesisType
    name: str = Field(min_length=1, max_length=255)


class ThresholdsBody(BaseModel):
    min_sources: int | None = Field(default=None, ge=0)
    min_foreign_sources: int | None = Field(default=None, ge=0)
    min_body_chars: int | None = Field(default=None, ge=0)
    max_body_chars: int | None = Field(default=None, ge=0)
    min_pages: int | None = Field(default=None, ge=0)
    max_pages: int | None = Field(default=None, ge=0)

    def to_domain(self) -> Thresholds:
        return Thresholds(**self.model_dump())


class DraftCreateRequest(BaseModel):
    """Every field optional: omitted ones start from the version in force."""

    rubric_md: str | None = None
    thresholds: ThresholdsBody | None = None
    effective_from: date | None = None


class DraftUpdateRequest(BaseModel):
    rubric_md: str | None = None
    thresholds: ThresholdsBody | None = None
    effective_from: date | None = None


# ---------- responses ----------


class UniversityResponse(BaseModel):
    id: uuid.UUID
    name: str
    short_name: str


class SourceResponse(BaseModel):
    filename: str
    sha256: str
    size: int
    downloadable: bool


class VersionSummaryResponse(BaseModel):
    id: uuid.UUID
    version_no: int
    status: str
    effective_from: date | None
    published_at: datetime | None
    created_at: datetime


class VersionResponse(VersionSummaryResponse):
    set_id: uuid.UUID
    set_name: str
    thesis_type: str
    university: UniversityResponse
    rubric_md: str
    thresholds: ThresholdsBody
    source: SourceResponse | None
    created_by: uuid.UUID
    published_by: uuid.UUID | None
    # The rubric is being drafted from the source (ADR 0025); and why the
    # last attempt failed, until the next one.
    drafting: bool = False
    drafting_error: str | None = None
    # What the model asks the admin to check in a drafted rubric.
    draft_notes: list[str] = []


class DraftRubricRequest(BaseModel):
    """Which of the admin's provider keys the draft runs on."""

    provider: str = Field(min_length=1, max_length=20)


class SetResponse(BaseModel):
    id: uuid.UUID
    name: str
    thesis_type: str
    university: UniversityResponse
    current: VersionSummaryResponse | None
    has_draft: bool


class SetDetailResponse(BaseModel):
    id: uuid.UUID
    name: str
    thesis_type: str
    university: UniversityResponse
    versions: list[VersionSummaryResponse]


def university_response(university: University) -> UniversityResponse:
    return UniversityResponse(
        id=university.id, name=university.name, short_name=university.short_name
    )


def version_summary(version: GuidelineVersion) -> VersionSummaryResponse:
    return VersionSummaryResponse(
        id=version.id,
        version_no=version.version_no,
        status=str(version.status),
        effective_from=version.effective_from,
        published_at=version.published_at,
        created_at=version.created_at,
    )


def set_response(summary: SetSummary) -> SetResponse:
    s = summary.guideline_set
    return SetResponse(
        id=s.id,
        name=s.name,
        thesis_type=str(s.thesis_type),
        university=university_response(summary.university),
        current=version_summary(summary.current) if summary.current else None,
        has_draft=summary.has_draft,
    )


def set_detail_response(detail: SetDetail) -> SetDetailResponse:
    s = detail.guideline_set
    return SetDetailResponse(
        id=s.id,
        name=s.name,
        thesis_type=str(s.thesis_type),
        university=university_response(detail.university),
        versions=[version_summary(v) for v in detail.versions],
    )


def version_response(detail: VersionDetail) -> VersionResponse:
    v = detail.version
    return VersionResponse(
        **version_summary(v).model_dump(),
        set_id=v.set_id,
        set_name=detail.guideline_set.name,
        thesis_type=str(detail.guideline_set.thesis_type),
        university=university_response(detail.university),
        rubric_md=v.rubric_md,
        thresholds=ThresholdsBody(**v.thresholds.to_dict()),
        source=SourceResponse(
            filename=v.source.filename,
            sha256=v.source.sha256,
            size=v.source.size,
            downloadable=v.source.file_id is not None,
        )
        if v.source
        else None,
        created_by=v.created_by,
        published_by=v.published_by,
        drafting=v.is_drafting,
        drafting_error=v.drafting_error or None,
        draft_notes=list(v.draft_notes) if v.is_draft else [],
    )
