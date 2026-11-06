"""How many times the broker has handed the worker one attempt of a task.

With late acks (ADR 0010) a task whose run kills its worker process — out of
memory on one thesis, a crash in a parser — is handed back and started again,
and kills the next one too, with no end. Celery's own retry count does not
see this: the run never got as far as asking for a retry. So the worker
counts deliveries itself, in Redis, per attempt: a retry is a new attempt
and starts from zero, a redelivery of the same attempt adds one.

Counting fails open. Without Redis the task could not have been delivered
either, and a lost count must not stop a run that would have worked.
"""

import redis
import structlog

from src.infrastructure.settings import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# A day: far longer than any attempt, and the key goes away on its own.
_TTL_SECONDS = 24 * 60 * 60


def _client() -> "redis.Redis":
    # redis-py leaves `**kwargs` and the shard hint untyped.
    return redis.Redis.from_url(  # pyright: ignore[reportUnknownMemberType]
        settings.redis_url, socket_timeout=2.0, socket_connect_timeout=1.0
    )


def count_delivery(task_name: str, task_id: str, attempt: int) -> int | None:
    """Add this delivery to the attempt's count and return the count.

    None when Redis could not be asked; the caller then runs the task.
    """
    key = f"corvus:deliveries:{task_name}:{task_id}:{attempt}"
    try:
        with (
            _client() as client,
            client.pipeline() as pipe,  # pyright: ignore[reportUnknownMemberType]
        ):
            pipe.incr(key)
            pipe.expire(key, _TTL_SECONDS)
            count, _ = pipe.execute()
        return int(count)
    except redis.RedisError as exc:
        logger.warning("delivery_count_failed", task_id=task_id, error=str(exc))
        return None
