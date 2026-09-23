"""Managing the guideline catalog — admin-only use cases.

Every write goes through the domain first, so a published version refuses to
change before anything reaches the database, and a publish — the old version
superseded, the new one published — lands in one commit.
"""

import uuid
from datetime import date
from uuid import UUID

import structlog

from src.document.extractor import CANONICAL_CONTENT_TYPE, detect_verified_format
from src.guidelines.application.exceptions import (
    GuidelineConflictError,
    GuidelineNotFoundError,
)
from src.guidelines.domain.catalog import (
    GuidelineSet,
    GuidelineVersion,
    SourceDocument,
    ThesisType,
    Thresholds,
    University,
)
from src.guidelines.infrastructure.repositories import CatalogRepository
from src.shared.files import FileStore

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class GuidelineAdminService:
    """Create universities and sets; draft, edit and publish versions."""

    def __init__(self, repo: CatalogRepository, files: FileStore) -> None:
        self._repo = repo
        self._files = files

    async def create_university(self, name: str, short_name: str) -> University:
        university = University(id=uuid.uuid4(), name=name, short_name=short_name)
        existing = {
            (u.name.lower(), u.short_name.lower())
            for u in await self._repo.list_universities()
        }
        if any(
            university.name.lower() == n or university.short_name.lower() == s
            for n, s in existing
        ):
            raise GuidelineConflictError(f"University already exists: {name!r}")
        await self._repo.add_university(university)
        await self._repo.commit()
        return university

    async def create_set(
        self, university_id: UUID, thesis_type: ThesisType, name: str
    ) -> GuidelineSet:
        if await self._repo.get_university(university_id) is None:
            raise GuidelineNotFoundError(str(university_id))
        guideline_set = GuidelineSet(
            id=uuid.uuid4(),
            university_id=university_id,
            thesis_type=thesis_type,
            name=name,
        )
        if await self._repo.find_set(
            university_id, str(thesis_type), guideline_set.name
        ):
            raise GuidelineConflictError(f"Set already exists: {name!r}")
        await self._repo.add_set(guideline_set)
        await self._repo.commit()
        return guideline_set

    async def create_draft(
        self,
        set_id: UUID,
        by: UUID,
        rubric_md: str | None = None,
        thresholds: Thresholds | None = None,
        effective_from: date | None = None,
    ) -> GuidelineVersion:
        """Open the next version of a set as a draft.

        Omitted rubric and thresholds are copied from the version in force, so
        a correction starts from what is there rather than from a blank page.
        One draft per set at a time: two would race to be published.
        """
        if await self._repo.get_set(set_id) is None:
            raise GuidelineNotFoundError(str(set_id))
        versions = await self._repo.list_versions(set_id)
        if any(v.is_draft for v in versions):
            raise GuidelineConflictError("This set already has a draft version")
        current = await self._repo.published_version(set_id)
        draft = GuidelineVersion(
            id=uuid.uuid4(),
            set_id=set_id,
            version_no=await self._repo.next_version_no(set_id),
            created_by=by,
            rubric_md=rubric_md
            if rubric_md is not None
            else (current.rubric_md if current else ""),
            thresholds=thresholds
            if thresholds is not None
            else (current.thresholds if current else Thresholds()),
            effective_from=effective_from,
        )
        await self._repo.add_version(draft)
        await self._repo.commit()
        return draft

    async def edit_draft(
        self,
        version_id: UUID,
        rubric_md: str | None = None,
        thresholds: Thresholds | None = None,
        effective_from: date | None = None,
    ) -> GuidelineVersion:
        """Change a draft. Raises VersionNotEditableError for anything else."""
        version = await self._require_version(version_id)
        version.edit(rubric_md, thresholds, effective_from)
        await self._repo.save_version(version)
        await self._repo.commit()
        return version

    async def attach_source(
        self, version_id: UUID, filename: str, data: bytes, content_type: str = ""
    ) -> GuidelineVersion:
        """Store the original regulation (PDF/DOCX) on a draft.

        Replacing an earlier upload deletes the old file in the same commit.
        """
        version = await self._require_version(version_id)
        fmt = detect_verified_format(data, filename, content_type)
        previous = version.source.file_id if version.source else None
        stored = await self._files.put(filename, CANONICAL_CONTENT_TYPE[fmt], data)
        version.attach_source(
            SourceDocument(
                file_id=stored.id,
                filename=stored.filename,
                sha256=stored.sha256,
                size=stored.size,
            )
        )
        await self._repo.save_version(version)
        if previous is not None:
            await self._files.delete(previous)
        await self._repo.commit()
        return version

    async def publish(self, version_id: UUID, by: UUID) -> GuidelineVersion:
        """Publish a draft; the version it replaces becomes superseded."""
        version = await self._require_version(version_id)
        current = await self._repo.published_version(version.set_id)
        version.publish(by)
        if current is not None:
            current.supersede()
            await self._repo.save_version(current)
        await self._repo.save_version(version)
        await self._repo.commit()
        logger.info(
            "guideline_version_published",
            set_id=str(version.set_id),
            version=version.version_no,
            superseded=current.version_no if current else None,
        )
        return version

    async def _require_version(self, version_id: UUID) -> GuidelineVersion:
        version = await self._repo.get_version(version_id)
        if version is None:
            raise GuidelineNotFoundError(str(version_id))
        return version
