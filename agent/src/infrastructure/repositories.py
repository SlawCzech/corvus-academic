"""Async repositories for the agent's own tables."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.models import AgentTaskModel, GuidelineChunkModel


class AgentTaskRepository:
    """Async CRUD operations for agent task records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, model: AgentTaskModel) -> None:
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)

    async def find_by_id(self, task_row_id: uuid.UUID) -> AgentTaskModel | None:
        return await self._session.get(AgentTaskModel, task_row_id)

    async def find_by_task_id(self, task_id: str) -> AgentTaskModel | None:
        result = await self._session.execute(
            select(AgentTaskModel).where(AgentTaskModel.task_id == task_id)
        )
        return result.scalar_one_or_none()

    async def find_by_user_and_task_id(
        self, user_id: uuid.UUID, task_id: str
    ) -> AgentTaskModel | None:
        result = await self._session.execute(
            select(AgentTaskModel).where(
                AgentTaskModel.user_id == user_id,
                AgentTaskModel.task_id == task_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        task_id: str,
        status: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> bool:
        """Write a task's status (and outcome) to its row.

        Returns False when no row matches — the caller decides whether that is
        worth an alert. ``result`` and ``error`` are only written when given,
        so a "running" update never clears an earlier value.
        """
        model = await self.find_by_task_id(task_id)
        if model is None:
            return False
        model.status = status
        if result is not None:
            model.result = result
        if error is not None:
            model.error = error
        model.updated_at = datetime.now(UTC)
        await self._session.commit()
        return True


class GuidelineChunkRepository:
    """Async store and similarity search for embedded requirement chunks."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_for_type(
        self,
        thesis_type: str,
        embedding_model: str,
        chunks: Sequence[GuidelineChunkModel],
    ) -> int:
        """Swap in a freshly ingested set for one thesis type and model.

        Ingestion is idempotent: running it twice leaves one copy, not two.
        Rows from a different embedding model are left alone — they belong to
        whoever is still using that model.
        """
        await self._session.execute(
            delete(GuidelineChunkModel).where(
                GuidelineChunkModel.thesis_type == thesis_type,
                GuidelineChunkModel.embedding_model == embedding_model,
            )
        )
        # Stamp the rows rather than trust them to agree with the arguments:
        # a mismatch here would delete one model's chunks and store another's.
        rows = list(chunks)
        for row in rows:
            row.thesis_type = thesis_type
            row.embedding_model = embedding_model
        self._session.add_all(rows)
        await self._session.commit()
        return len(rows)

    async def count(self, thesis_type: str, embedding_model: str) -> int:
        """Return how many chunks are stored for this type and model."""
        result = await self._session.execute(
            select(func.count())
            .select_from(GuidelineChunkModel)
            .where(
                GuidelineChunkModel.thesis_type == thesis_type,
                GuidelineChunkModel.embedding_model == embedding_model,
            )
        )
        return int(result.scalar_one())

    async def search(
        self,
        thesis_type: str,
        embedding: Sequence[float],
        embedding_model: str,
        limit: int,
    ) -> list[GuidelineChunkModel]:
        """Return the chunks that bear on this thesis, in document order.

        Always-include chunks come back whatever the distances say: they carry
        the rules the judgement itself is defined by. The rest are the nearest
        `limit` by cosine distance. The result is ordered by section so the
        prompt reads like the document, not like a ranking.
        """
        pinned = await self._session.execute(
            select(GuidelineChunkModel).where(
                GuidelineChunkModel.thesis_type == thesis_type,
                GuidelineChunkModel.embedding_model == embedding_model,
                GuidelineChunkModel.always_include.is_(True),
            )
        )
        nearest = await self._session.execute(
            select(GuidelineChunkModel)
            .where(
                GuidelineChunkModel.thesis_type == thesis_type,
                GuidelineChunkModel.embedding_model == embedding_model,
                GuidelineChunkModel.always_include.is_(False),
            )
            .order_by(GuidelineChunkModel.embedding.cosine_distance(embedding))
            .limit(limit)
        )
        found = {c.id: c for c in pinned.scalars().all()}
        found.update({c.id: c for c in nearest.scalars().all()})
        return sorted(found.values(), key=lambda c: c.section)
