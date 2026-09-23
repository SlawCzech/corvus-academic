"""Fixtures for the guideline catalog tests — the app-wide ones mentoring built.

One in-memory database with every context's tables and the three seeded
users (admin, two promoters); the catalog needs both roles to test who may
read and who may write.
"""

from tests.test_mentoring.conftest import client, db_session

__all__ = ["client", "db_session"]
