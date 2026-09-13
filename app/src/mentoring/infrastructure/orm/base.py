"""Shared declarative base and schema name for the mentoring ORM models.

Split out from the tables themselves so two files on opposite sides of a
foreign key (``student.py`` and ``action.py``) can each depend on this one
without depending on each other.
"""

from sqlalchemy.orm import DeclarativeBase

SCHEMA = "mentoring"


class Base(DeclarativeBase):
    """Shared declarative base for all mentoring ORM models."""
