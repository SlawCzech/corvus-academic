"""The guideline catalog, seen through mentoring's `GuidelineSource` port."""

from uuid import UUID

from src.guidelines.application.catalog import GuidelineCatalog
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
        return GuidelineRubric(version_id=version.id, rubric_md=version.rubric_md)
