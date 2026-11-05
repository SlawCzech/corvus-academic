"""The guideline catalog, seen through mentoring's `GuidelineSource` port."""

from uuid import UUID

from src.guidelines.application.catalog import GuidelineCatalog
from src.guidelines.domain.rubric import RubricShapeError, parse_rubric
from src.mentoring.application.guidelines_port import GuidelineRubric


class CatalogGuidelineSource:
    """Adapts `GuidelineCatalog` to what mentoring asks of it."""

    def __init__(self, catalog: GuidelineCatalog) -> None:
        self._catalog = catalog

    async def thesis_type_of(self, set_id: UUID) -> str | None:
        guideline_set = await self._catalog.get_set(set_id)
        if guideline_set is None or await self._catalog.current_version(set_id) is None:
            return None
        return str(guideline_set.thesis_type)

    async def current_rubric(self, set_id: UUID) -> GuidelineRubric | None:
        version = await self._catalog.current_version(set_id)
        if version is None:
            return None
        try:
            sections: dict[str, str] | None = parse_rubric(version.rubric_md).to_dict()
        except RubricShapeError:
            # Published before rubrics had sections: it still judges, whole.
            sections = None
        return GuidelineRubric(
            version_id=version.id,
            rubric_md=version.rubric_md,
            thresholds=version.thresholds.to_dict(),
            sections=sections,
        )

    async def first_set_for(self, thesis_type: str) -> UUID | None:
        summaries = await self._catalog.list_sets(thesis_type)
        return summaries[0].guideline_set.id if summaries else None
