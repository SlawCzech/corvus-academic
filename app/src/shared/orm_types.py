"""Column types shared by every context's ORM models."""

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


class UtcDateTime(TypeDecorator[datetime]):
    """``DateTime(timezone=True)`` that always reads back aware, in UTC.

    Postgres keeps the zone; SQLite (the tests) drops it, and a naive value
    read back from there cannot be compared with ``datetime.now(UTC)``.
    Every timestamp Corvus stores is UTC, so a naive one is read as UTC.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        if value is None or value.tzinfo is None:
            return value
        return value.astimezone(UTC)

    def process_result_value(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value
