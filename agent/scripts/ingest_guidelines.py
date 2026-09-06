"""Ingest the university requirements into the vector store.

Run after changing a requirements document, or after changing
`EMBEDDING_MODEL`:

    docker compose -f infra/docker-compose.yml run --rm agent \
        python scripts/ingest_guidelines.py

Idempotent: each run replaces the chunks for the thesis types it ingests,
under the embedding model currently configured. Rows belonging to another
model are left where they are — whoever still runs that model still needs
them.
"""

import asyncio
import sys
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.application.guidelines import load_guidelines, split_into_chunks
from src.domain.analysis import ThesisType
from src.infrastructure.embeddings import embed_documents
from src.infrastructure.models import GuidelineChunkModel
from src.infrastructure.repositories import GuidelineChunkRepository
from src.infrastructure.settings import settings


async def ingest(thesis_type: str) -> int:
    """Chunk, embed and store one requirements document."""
    chunks = split_into_chunks(load_guidelines(thesis_type))
    if not chunks:
        print(f"  {thesis_type}: nothing to ingest")
        return 0

    vectors = embed_documents([c.text for c in chunks])
    now = datetime.now(UTC)
    rows = [
        GuidelineChunkModel(
            id=uuid.uuid4(),
            thesis_type=thesis_type,
            section=chunk.section,
            chunk_text=chunk.text,
            embedding_model=settings.embedding_model,
            dimensions=len(vector),
            embedding=vector,
            always_include=chunk.always_include,
            created_at=now,
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            stored = await GuidelineChunkRepository(session).replace_for_type(
                thesis_type, settings.embedding_model, rows
            )
    finally:
        await engine.dispose()

    pinned = sum(1 for c in chunks if c.always_include)
    print(
        f"  {thesis_type}: {stored} chunks "
        f"({pinned} always included, {len(vectors[0])} dimensions)"
    )
    return stored


async def main() -> int:
    """Ingest every known thesis type."""
    print(f"Embedding model: {settings.embedding_model}")
    total = 0
    for thesis_type in ThesisType:
        total += await ingest(str(thesis_type))
    print(f"Done: {total} chunks stored.")
    return 0 if total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
