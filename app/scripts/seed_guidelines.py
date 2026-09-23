"""Load UE Katowice's thesis requirements into the guideline catalog.

Creates the university, one set per thesis type, and publishes the rubrics in
`scripts/seed_data/guidelines/` as version 1 — the same text the agent's static
files carry, with Corvus's own severity rules marked as such. Idempotent: a set
that already has any version is left alone, so an admin's later versions are
never overwritten.

    python scripts/seed_guidelines.py
"""

import asyncio
import sys
import uuid
from pathlib import Path

from sqlalchemy import text

from src.guidelines.application.admin_service import GuidelineAdminService
from src.guidelines.domain.catalog import ThesisType, Thresholds
from src.guidelines.infrastructure.orm import SourceFileModel
from src.guidelines.infrastructure.repositories import CatalogRepository
from src.shared.database import session_factory
from src.shared.settings import settings
from src.shared.sql_file_store import SqlFileStore

_DATA = Path(__file__).parent / "seed_data" / "guidelines"

_UNIVERSITY = ("Uniwersytet Ekonomiczny w Katowicach", "UE Katowice")

# Name, rubric file and the numbers the rubric states, as data code can check.
_SETS: dict[ThesisType, tuple[str, str, Thresholds]] = {
    ThesisType.BACHELOR: (
        "Prace licencjackie (zarządzenie 117/22, zał. 1)",
        "bachelor.md",
        Thresholds(
            min_sources=25,
            min_foreign_sources=4,
            min_body_chars=80_000,
            max_body_chars=130_000,
        ),
    ),
    ThesisType.MASTER_ARTICLE: (
        "Prace magisterskie — forma artykułu (zarządzenie 117/22, zał. 2)",
        "master_article.md",
        Thresholds(
            min_sources=40,
            min_foreign_sources=8,
            min_body_chars=55_000,
            max_body_chars=65_000,
        ),
    ),
}


async def seed() -> None:
    async with session_factory() as session:
        row = await session.execute(
            text("SELECT id FROM identity.users WHERE email = :email"),
            {"email": settings.admin_email},
        )
        admin_id: uuid.UUID = row.scalar_one_or_none() or uuid.UUID(int=0)

        repo = CatalogRepository(session)
        svc = GuidelineAdminService(repo, SqlFileStore(session, SourceFileModel))

        name, short_name = _UNIVERSITY
        university = await repo.find_university_by_short_name(short_name)
        if university is None:
            university = await svc.create_university(name, short_name)
            print(f"University {short_name!r} created")

        for thesis_type, (set_name, filename, thresholds) in _SETS.items():
            existing = await repo.find_set(university.id, str(thesis_type), set_name)
            guideline_set = existing or await svc.create_set(
                university.id, thesis_type, set_name
            )
            if await repo.list_versions(guideline_set.id):
                print(f"{set_name!r} already has versions — skipping")
                continue
            draft = await svc.create_draft(
                guideline_set.id,
                admin_id,
                rubric_md=(_DATA / filename).read_text(encoding="utf-8"),
                thresholds=thresholds,
            )
            await svc.publish(draft.id, admin_id)
            print(f"{set_name!r}: version 1 published")


if __name__ == "__main__":
    asyncio.run(seed())
    sys.exit(0)
