"""Reading guideline chunks from Postgres, from synchronous code.

The Celery worker is synchronous while the rest of the service speaks async
SQLAlchemy, so — as with `task_status` — each read opens its own short-lived
engine. Retrieval happens once per action, next to an LLM call measured in
minutes.
"""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass

import structlog
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.infrastructure.repositories import GuidelineChunkRepository
from src.infrastructure.settings import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class StoredChunk:
    """One retrieved requirement section."""

    section: str
    text: str


async def _search(
    thesis_type: str,
    embedding: Sequence[float],
    embedding_model: str,
    limit: int,
) -> list[StoredChunk]:
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            found = await GuidelineChunkRepository(session).search(
                thesis_type, embedding, embedding_model, limit
            )
            return [StoredChunk(section=c.section, text=c.chunk_text) for c in found]
    finally:
        await engine.dispose()


def search_chunks(
    thesis_type: str,
    embedding: Sequence[float],
    embedding_model: str,
    limit: int,
) -> list[StoredChunk]:
    """Return the stored chunks nearest to an embedding, or none on failure.

    A retrieval that cannot run is not a reason to fail an action: the caller
    falls back to the requirements file, which is what every action used
    before this table existed.
    """
    try:
        return asyncio.run(
            _search(thesis_type, embedding, embedding_model, limit)
        )
    except Exception as exc:
        logger.error(
            "guideline_search_failed", thesis_type=thesis_type, error=str(exc)
        )
        return []
