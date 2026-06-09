"""SQLAlchemy ORM models for the gateway service.

Gateway no longer owns any domain data — analysis records moved to the
agent service (analysis.* schema). This file is kept for Alembic tooling
compatibility; Base.metadata is empty after the gateway.analyses table
was dropped in migration 0002.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for gateway ORM models."""
