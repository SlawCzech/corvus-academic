"""Async repositories for the guideline catalog.

They map rows to domain objects themselves — the catalog is small and has no
second consumer of its rows — and commit only when asked, so a publish that
supersedes one version and publishes another is one transaction.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.guidelines.domain.catalog import (
    GuidelineSet,
    GuidelineVersion,
    SourceDocument,
    ThesisType,
    Thresholds,
    University,
    VersionStatus,
)
from src.guidelines.infrastructure.orm import (
    GuidelineSetModel,
    GuidelineVersionModel,
    UniversityModel,
)


def _university(model: UniversityModel) -> University:
    return University(id=model.id, name=model.name, short_name=model.short_name)


def _set(model: GuidelineSetModel) -> GuidelineSet:
    return GuidelineSet(
        id=model.id,
        university_id=model.university_id,
        thesis_type=ThesisType(model.thesis_type),
        name=model.name,
    )


def _version(model: GuidelineVersionModel) -> GuidelineVersion:
    source = (
        SourceDocument(
            file_id=model.source_file_id,
            filename=model.source_filename,
            sha256=model.source_sha256 or "",
            size=model.source_size or 0,
        )
        if model.source_filename is not None
        else None
    )
    return GuidelineVersion(
        id=model.id,
        set_id=model.set_id,
        version_no=model.version_no,
        created_by=model.created_by,
        rubric_md=model.rubric_md,
        thresholds=Thresholds.from_dict(model.thresholds),
        effective_from=model.effective_from,
        source=source,
        status=VersionStatus(model.status),
        created_at=model.created_at,
        published_by=model.published_by,
        published_at=model.published_at,
        drafting_task_id=model.drafting_task_id,
        drafting_error=model.drafting_error,
    )


def _write_version(model: GuidelineVersionModel, version: GuidelineVersion) -> None:
    model.id = version.id
    model.set_id = version.set_id
    model.version_no = version.version_no
    model.status = str(version.status)
    model.rubric_md = version.rubric_md
    model.thresholds = version.thresholds.to_dict()
    model.effective_from = version.effective_from
    model.source_file_id = version.source.file_id if version.source else None
    model.source_filename = version.source.filename if version.source else None
    model.source_sha256 = version.source.sha256 if version.source else None
    model.source_size = version.source.size if version.source else None
    model.created_by = version.created_by
    model.created_at = version.created_at
    model.published_by = version.published_by
    model.drafting_task_id = version.drafting_task_id
    model.drafting_error = version.drafting_error
    model.published_at = version.published_at


class CatalogRepository:
    """Universities, sets and versions — one repository for one small aggregate
    family, because a publish touches two versions of one set at once."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()

    # ---------- universities ----------

    async def add_university(self, university: University) -> None:
        self._session.add(
            UniversityModel(
                id=university.id,
                name=university.name,
                short_name=university.short_name,
            )
        )
        await self._session.flush()

    async def list_universities(self) -> list[University]:
        result = await self._session.execute(
            select(UniversityModel).order_by(UniversityModel.name)
        )
        return [_university(m) for m in result.scalars().all()]

    async def get_university(self, university_id: uuid.UUID) -> University | None:
        model = await self._session.get(UniversityModel, university_id)
        return _university(model) if model else None

    async def find_university_by_short_name(self, short_name: str) -> University | None:
        result = await self._session.execute(
            select(UniversityModel).where(UniversityModel.short_name == short_name)
        )
        model = result.scalar_one_or_none()
        return _university(model) if model else None

    # ---------- sets ----------

    async def add_set(self, guideline_set: GuidelineSet) -> None:
        self._session.add(
            GuidelineSetModel(
                id=guideline_set.id,
                university_id=guideline_set.university_id,
                thesis_type=str(guideline_set.thesis_type),
                name=guideline_set.name,
            )
        )
        await self._session.flush()

    async def get_set(self, set_id: uuid.UUID) -> GuidelineSet | None:
        model = await self._session.get(GuidelineSetModel, set_id)
        return _set(model) if model else None

    async def find_set(
        self, university_id: uuid.UUID, thesis_type: str, name: str
    ) -> GuidelineSet | None:
        result = await self._session.execute(
            select(GuidelineSetModel).where(
                GuidelineSetModel.university_id == university_id,
                GuidelineSetModel.thesis_type == thesis_type,
                GuidelineSetModel.name == name,
            )
        )
        model = result.scalar_one_or_none()
        return _set(model) if model else None

    async def list_sets(self, thesis_type: str | None = None) -> list[GuidelineSet]:
        stmt = select(GuidelineSetModel).order_by(
            GuidelineSetModel.thesis_type, GuidelineSetModel.name
        )
        if thesis_type is not None:
            stmt = stmt.where(GuidelineSetModel.thesis_type == thesis_type)
        result = await self._session.execute(stmt)
        return [_set(m) for m in result.scalars().all()]

    # ---------- versions ----------

    async def add_version(self, version: GuidelineVersion) -> None:
        model = GuidelineVersionModel()
        _write_version(model, version)
        self._session.add(model)
        await self._session.flush()

    async def save_version(self, version: GuidelineVersion) -> None:
        """Write a changed version back onto its row. Flushes, does not commit."""
        model = await self._session.get(GuidelineVersionModel, version.id)
        if model is None:  # pragma: no cover — callers load before saving
            raise LookupError(str(version.id))
        _write_version(model, version)
        await self._session.flush()

    async def get_version(self, version_id: uuid.UUID) -> GuidelineVersion | None:
        model = await self._session.get(GuidelineVersionModel, version_id)
        return _version(model) if model else None

    async def list_versions(self, set_id: uuid.UUID) -> list[GuidelineVersion]:
        """A set's versions, newest first."""
        result = await self._session.execute(
            select(GuidelineVersionModel)
            .where(GuidelineVersionModel.set_id == set_id)
            .order_by(GuidelineVersionModel.version_no.desc())
        )
        return [_version(m) for m in result.scalars().all()]

    async def published_version(self, set_id: uuid.UUID) -> GuidelineVersion | None:
        result = await self._session.execute(
            select(GuidelineVersionModel).where(
                GuidelineVersionModel.set_id == set_id,
                GuidelineVersionModel.status == str(VersionStatus.PUBLISHED),
            )
        )
        model = result.scalar_one_or_none()
        return _version(model) if model else None

    async def next_version_no(self, set_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.max(GuidelineVersionModel.version_no)).where(
                GuidelineVersionModel.set_id == set_id
            )
        )
        current: int | None = result.scalar_one_or_none()
        return (current or 0) + 1
