"""Reading the guideline catalog — what promoters, and mentoring, use.

Drafts are visible only to callers who manage the catalog: a promoter sees a
set's published and superseded versions, never work in progress.
"""

from dataclasses import dataclass
from uuid import UUID

from src.guidelines.application.exceptions import GuidelineNotFoundError
from src.guidelines.domain.catalog import (
    GuidelineSet,
    GuidelineVersion,
    University,
)
from src.guidelines.infrastructure.repositories import CatalogRepository
from src.shared.files import FileStore, StoredFile


@dataclass(frozen=True)
class SetSummary:
    """A set as a list shows it: where it is from and what is in force."""

    guideline_set: GuidelineSet
    university: University
    current: GuidelineVersion | None
    has_draft: bool


@dataclass(frozen=True)
class SetDetail:
    guideline_set: GuidelineSet
    university: University
    versions: list[GuidelineVersion]


@dataclass(frozen=True)
class VersionDetail:
    version: GuidelineVersion
    guideline_set: GuidelineSet
    university: University


class GuidelineCatalog:
    """Read access to universities, sets and versions."""

    def __init__(self, repo: CatalogRepository, files: FileStore) -> None:
        self._repo = repo
        self._files = files

    async def list_universities(self) -> list[University]:
        return await self._repo.list_universities()

    async def list_sets(
        self, thesis_type: str | None = None, include_drafts: bool = False
    ) -> list[SetSummary]:
        """Every set, optionally of one thesis type, with its version in force."""
        summaries: list[SetSummary] = []
        for guideline_set in await self._repo.list_sets(thesis_type):
            versions = await self._repo.list_versions(guideline_set.id)
            has_draft = any(v.is_draft for v in versions)
            if not include_drafts and not any(not v.is_draft for v in versions):
                # Nothing a promoter could pick or read yet.
                continue
            summaries.append(
                SetSummary(
                    guideline_set=guideline_set,
                    university=await self._university(guideline_set.university_id),
                    current=await self._repo.published_version(guideline_set.id),
                    has_draft=has_draft and include_drafts,
                )
            )
        return summaries

    async def get_set_detail(
        self, set_id: UUID, include_drafts: bool = False
    ) -> SetDetail:
        guideline_set = await self._require_set(set_id)
        versions = [
            v
            for v in await self._repo.list_versions(set_id)
            if include_drafts or not v.is_draft
        ]
        if not versions and not include_drafts:
            raise GuidelineNotFoundError(str(set_id))
        return SetDetail(
            guideline_set=guideline_set,
            university=await self._university(guideline_set.university_id),
            versions=versions,
        )

    async def get_version(
        self, version_id: UUID, include_drafts: bool = False
    ) -> VersionDetail:
        version = await self._repo.get_version(version_id)
        if version is None or (version.is_draft and not include_drafts):
            raise GuidelineNotFoundError(str(version_id))
        guideline_set = await self._require_set(version.set_id)
        return VersionDetail(
            version=version,
            guideline_set=guideline_set,
            university=await self._university(guideline_set.university_id),
        )

    async def download_source(
        self, version_id: UUID, include_drafts: bool = False
    ) -> tuple[StoredFile, bytes]:
        """The original regulation of a version."""
        detail = await self.get_version(version_id, include_drafts)
        source = detail.version.source
        if source is None or source.file_id is None:
            raise GuidelineNotFoundError(f"{version_id} has no source document")
        found = await self._files.get(source.file_id)
        if found is None:
            raise GuidelineNotFoundError(f"{version_id} has no source document")
        return found

    # ---------- for mentoring ----------

    async def get_set(self, set_id: UUID) -> GuidelineSet | None:
        return await self._repo.get_set(set_id)

    async def current_version(self, set_id: UUID) -> GuidelineVersion | None:
        """The published version actions are judged against today, if any."""
        return await self._repo.published_version(set_id)

    # ---------- internals ----------

    async def _require_set(self, set_id: UUID) -> GuidelineSet:
        guideline_set = await self._repo.get_set(set_id)
        if guideline_set is None:
            raise GuidelineNotFoundError(str(set_id))
        return guideline_set

    async def _university(self, university_id: UUID) -> University:
        university = await self._repo.get_university(university_id)
        if university is None:  # pragma: no cover — guarded by a foreign key
            raise GuidelineNotFoundError(str(university_id))
        return university
