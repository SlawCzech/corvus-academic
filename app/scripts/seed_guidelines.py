"""Load UE Katowice's thesis requirements into the guideline catalog.

Creates the university, one set per thesis type, and publishes the rubrics in
`scripts/seed_data/guidelines/` — Polish, read from Zarządzenie Nr 117/22, with
Corvus's own severity rules marked as such — together with the original
regulation files.

    python scripts/seed_guidelines.py            # fill an empty catalog
    python scripts/seed_guidelines.py --update   # roll changed seed data out

Without `--update` a set that already has any version is left alone, so an
admin's own versions are never touched. With it, a set whose version in force
differs from the seed data (rubric, thresholds or original file) gets a new
version published from the seed data — the previous one becomes superseded,
exactly as if an admin had published it. Run it only when the seed data is
meant to win over what is in the catalog.
"""

import argparse
import asyncio
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text

from src.guidelines.application.admin_service import GuidelineAdminService
from src.guidelines.domain.catalog import GuidelineVersion, ThesisType, Thresholds
from src.guidelines.infrastructure.orm import SourceFileModel
from src.guidelines.infrastructure.repositories import CatalogRepository
from src.shared.database import session_factory
from src.shared.files import sha256_hex
from src.shared.settings import settings
from src.shared.sql_file_store import SqlFileStore

_DATA = Path(__file__).parent / "seed_data" / "guidelines"

_UNIVERSITY = ("Uniwersytet Ekonomiczny w Katowicach", "UE Katowice")


@dataclass(frozen=True)
class _SeedSet:
    name: str
    rubric_file: str
    thresholds: Thresholds
    source_file: str
    # The name the original is stored and downloaded under.
    source_name: str

    def rubric(self) -> str:
        return (_DATA / self.rubric_file).read_text(encoding="utf-8")

    def source(self) -> bytes:
        return (_DATA / self.source_file).read_bytes()


_SETS: dict[ThesisType, _SeedSet] = {
    ThesisType.BACHELOR: _SeedSet(
        name="Prace licencjackie (zarządzenie 117/22, zał. 1)",
        rubric_file="bachelor.md",
        thresholds=Thresholds(
            min_sources=25,
            min_foreign_sources=4,
            min_body_chars=80_000,
            max_body_chars=130_000,
        ),
        source_file="zarzadzenie_117_22_zal_1.docx",
        source_name="Zarządzenie Nr 117-22 — załącznik Nr 1.docx",
    ),
    ThesisType.MASTER_ARTICLE: _SeedSet(
        name="Prace magisterskie — forma artykułu (zarządzenie 117/22, zał. 2)",
        rubric_file="master_article.md",
        thresholds=Thresholds(
            min_sources=40,
            min_foreign_sources=8,
            min_body_chars=55_000,
            max_body_chars=65_000,
        ),
        source_file="zarzadzenie_117_22_zal_2.docx",
        source_name="Zarządzenie Nr 117-22 — załącznik Nr 2.docx",
    ),
}


def _differs(current: GuidelineVersion, seed: _SeedSet) -> bool:
    """Whether the version in force is not what the seed data says."""
    return (
        current.rubric_md != seed.rubric()
        or current.thresholds != seed.thresholds
        or current.source is None
        or current.source.sha256 != sha256_hex(seed.source())
    )


async def _publish(
    svc: GuidelineAdminService, set_id: uuid.UUID, seed: _SeedSet, by: uuid.UUID
) -> GuidelineVersion:
    draft = await svc.create_draft(
        set_id, by, rubric_md=seed.rubric(), thresholds=seed.thresholds
    )
    await svc.attach_source(draft.id, seed.source_name, seed.source())
    return await svc.publish(draft.id, by)


async def seed(update: bool) -> None:
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

        for thesis_type, seed_set in _SETS.items():
            existing = await repo.find_set(
                university.id, str(thesis_type), seed_set.name
            )
            guideline_set = existing or await svc.create_set(
                university.id, thesis_type, seed_set.name
            )
            current = await repo.published_version(guideline_set.id)

            if not await repo.list_versions(guideline_set.id):
                version = await _publish(svc, guideline_set.id, seed_set, admin_id)
                print(f"{seed_set.name!r}: version {version.version_no} published")
            elif not update:
                print(f"{seed_set.name!r} already has versions — skipping")
            elif current is not None and not _differs(current, seed_set):
                print(f"{seed_set.name!r} matches the seed data — nothing to do")
            else:
                version = await _publish(svc, guideline_set.id, seed_set, admin_id)
                print(
                    f"{seed_set.name!r}: version {version.version_no} published "
                    f"from the seed data"
                )


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the guideline catalog.")
    parser.add_argument(
        "--update",
        action="store_true",
        help="publish a new version where the catalog differs from the seed data",
    )
    asyncio.run(seed(parser.parse_args().update))
    return 0


if __name__ == "__main__":
    sys.exit(main())
