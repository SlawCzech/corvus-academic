"""ORM model for the admin's local-model allowlist.

Mirrors ``domain/model_policy.py``. A model with no row is installed but not
offered — the admin opts models in, never out of a list they never saw.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Index, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from src.mentoring.infrastructure.orm.base import SCHEMA, Base


class ModelSettingModel(Base):
    __tablename__ = "model_settings"
    __table_args__ = (
        # At most one default. Partial unique index on both dialects, so the
        # SQLite test engine refuses a second default just like Postgres.
        Index(
            "uq_mentoring_model_settings_default",
            "is_default",
            unique=True,
            postgresql_where=text("is_default"),
            sqlite_where=text("is_default"),
        ),
        {"schema": SCHEMA},
    )

    name: Mapped[str] = mapped_column(String(200), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
