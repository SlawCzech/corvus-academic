"""Running the retention sweep: once on demand, or on a timer in-process.

The timer lives in `app` because the data does — `agent`'s Celery beat would
have to reach across into the mentoring schema. One sweep a day is plenty for
rules measured in weeks and months, and the sweep is idempotent, so two
replicas each running it cost nothing but a query.
"""

import asyncio
from datetime import UTC, datetime

import structlog

from src.mentoring.application.retention_service import RetentionService
from src.mentoring.infrastructure.orm import DraftFileModel
from src.mentoring.infrastructure.repositories import (
    StudentRepository,
    ThesisDraftRepository,
)
from src.shared.database import session_factory
from src.shared.sql_file_store import SqlFileStore

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def sweep_once(now: datetime | None = None) -> int:
    """Run one sweep in a fresh session; return how many versions were purged."""
    async with session_factory() as session:
        service = RetentionService(
            StudentRepository(session),
            ThesisDraftRepository(session),
            SqlFileStore(session, DraftFileModel),
        )
        return await service.sweep(now or datetime.now(UTC))


async def run_retention_sweeps(interval_hours: float) -> None:
    """Sweep now, then every ``interval_hours``, until cancelled.

    A failed sweep is logged and retried at the next interval — a database
    blip must not take the loop, or the process, down with it.
    """
    while True:
        try:
            await sweep_once()
        except Exception as exc:
            logger.error("retention_sweep_failed", error=str(exc))
        await asyncio.sleep(interval_hours * 3600)
