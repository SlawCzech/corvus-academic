"""Shared test fixtures for gateway tests."""

import os
import uuid
from collections.abc import AsyncGenerator

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("JWT_SECRET", "test-secret-key-that-is-long-enough-32ch")
os.environ.setdefault("FERNET_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")

from main import app  # noqa: E402
from src.infrastructure.database import get_db_session  # noqa: E402
from src.infrastructure.models import Base, UserModel  # noqa: E402

_SQLITE_URL = "sqlite+aiosqlite:///:memory:"

ADMIN_UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")
PROMOTOR_UUID = uuid.UUID("00000000-0000-0000-0000-000000000002")
ADMIN_EMAIL = "admin@corvus.local"
ADMIN_PASSWORD = "admin-secret"
PROMOTOR_EMAIL = "promotor@corvus.local"
PROMOTOR_PASSWORD = "promotor-secret"


def _hash(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """In-memory SQLite session pre-seeded with admin and promotor users."""
    engine = create_async_engine(_SQLITE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(
            UserModel(
                id=ADMIN_UUID,
                email=ADMIN_EMAIL,
                role="admin",
                hashed_password=_hash(ADMIN_PASSWORD),
            )
        )
        session.add(
            UserModel(
                id=PROMOTOR_UUID,
                email=PROMOTOR_EMAIL,
                role="promotor",
                hashed_password=_hash(PROMOTOR_PASSWORD),
            )
        )
        await session.commit()
        yield session
    await engine.dispose()


@pytest.fixture
def client(db_session: AsyncSession) -> TestClient:
    """TestClient with the DB session dependency pointing to in-memory SQLite."""

    async def _override() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override
    tc = TestClient(app)
    yield tc
    app.dependency_overrides.pop(get_db_session, None)
