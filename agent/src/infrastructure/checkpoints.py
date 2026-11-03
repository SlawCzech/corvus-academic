"""Graph checkpoints in Postgres — a run that dies resumes where it stopped.

LangGraph saves the state after every step (and, within a step of parallel
branches, the writes of each branch that finished). With a checkpointer the
graph can be invoked again with no input and the same ``thread_id``, and it
continues from the last saved step instead of starting over. For a review
that is the difference between redoing three analyses, and paying for them
twice, and redoing only the one that had not finished.

The thread is the Celery task id: a retry of the task, or a redelivery after
the worker died, runs under the same id and so finds its own checkpoints.

What is stored is the graph state, and the state holds the thesis text. So
checkpoints are deleted as soon as a run ends (`delete`), and with the
action when a promoter hard-deletes it (ADR 0009). The user's own provider
key is never in the state — it lives in a ContextVar (`llm_factory`).

Deserialising from a database is where arbitrary objects get built, so the
serializer is given the exact domain types the state may contain and nothing
else.
"""

from __future__ import annotations

from collections.abc import Generator, Iterable
from contextlib import contextmanager

import psycopg
import structlog
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from psycopg.rows import DictRow, dict_row

from src.infrastructure.settings import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Every non-builtin type that can appear in ActionState. A checkpoint holding
# anything else fails to load rather than instantiating it.
_STATE_TYPES: list[tuple[str, str]] = [
    ("src.domain.action", "ActionType"),
    ("src.domain.analysis", "Finding"),
    ("src.domain.analysis", "FindingSeverity"),
    ("src.domain.analysis", "FindingSource"),
    ("src.domain.review", "Score"),
]

_setup_done = False


def serializer() -> JsonPlusSerializer:
    """The serde every checkpointer here uses: domain types allow-listed."""
    return JsonPlusSerializer(allowed_msgpack_modules=_STATE_TYPES)


def _conninfo() -> str:
    # The service speaks asyncpg through SQLAlchemy; the checkpointer is sync
    # psycopg. Same database, same credentials, different driver prefix.
    return settings.database_url.replace("+asyncpg", "", 1)


def _connect() -> psycopg.Connection[DictRow]:
    return psycopg.Connection[DictRow].connect(
        _conninfo(),
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
        # Next to the agent's other tables, not in `public`.
        options="-c search_path=analysis",
    )


@contextmanager
def open_checkpointer() -> Generator[PostgresSaver | None]:
    """A checkpointer for one task's run, or None when checkpoints are off.

    None, not an error, when the database will not have it: a run without
    checkpoints is the run every action had before this existed — it just
    cannot resume.
    """
    if not settings.checkpoints_enabled:
        yield None
        return
    try:
        conn = _connect()
    except Exception as exc:
        logger.warning("checkpointer_unavailable", error=str(exc))
        yield None
        return
    with conn:
        saver = PostgresSaver(conn, serde=serializer())
        global _setup_done
        if not _setup_done:
            # Creates or migrates the checkpoint tables; idempotent, and
            # cheap after the first time, but once per process is enough.
            saver.setup()
            _setup_done = True
        yield saver


def delete(thread_ids: Iterable[str]) -> None:
    """Delete the checkpoints of these threads (task ids), if there are any.

    Swallows failures: an action deleted while the database blinks keeps a
    few rows of checkpoint until the next delete — worth a warning, not a 500.
    """
    ids = [t for t in thread_ids if t]
    if not ids or not settings.checkpoints_enabled:
        return
    try:
        with open_checkpointer() as saver:
            if saver is None:
                return
            for thread_id in ids:
                saver.delete_thread(thread_id)
    except Exception as exc:
        logger.warning("checkpoint_delete_failed", count=len(ids), error=str(exc))
