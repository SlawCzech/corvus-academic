"""Shared fixtures for mentoring tests.

Environment defaults live in the parent `tests/conftest.py`.

Both bounded contexts' tables are created in the one in-memory SQLite
database: the mentoring endpoints authenticate with real JWTs obtained from
`POST /auth/login`, which needs `identity.users`.
"""

import uuid
from collections.abc import AsyncGenerator, Generator

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from main import app
from src.identity.infrastructure.limiter import login_rate_limit
from src.identity.infrastructure.models import Base as IdentityBase
from src.identity.infrastructure.models import UserModel
from src.mentoring.infrastructure.orm import Base as MentoringBase
from src.shared.database import get_db_session

# Both schemas translate to None so SQLite — which has no schemas — can hold
# the tables. Extends the map already used by the identity tests.
_SQLITE_URL = "sqlite+aiosqlite:///:memory:"
_SCHEMA_TRANSLATE = {"schema_translate_map": {"identity": None, "mentoring": None}}

ADMIN_UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")
PROMOTOR_UUID = uuid.UUID("00000000-0000-0000-0000-000000000002")
OTHER_PROMOTOR_UUID = uuid.UUID("00000000-0000-0000-0000-000000000003")
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin-secret"
PROMOTOR_EMAIL = "promotor@example.com"
PROMOTOR_PASSWORD = "promotor-secret"
OTHER_PROMOTOR_EMAIL = "other@example.com"
OTHER_PROMOTOR_PASSWORD = "other-secret"


def _hash(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """In-memory SQLite session with identity + mentoring tables, seeded users."""
    engine = create_async_engine(_SQLITE_URL, execution_options=_SCHEMA_TRANSLATE)
    async with engine.begin() as conn:
        await conn.run_sync(IdentityBase.metadata.create_all)
        await conn.run_sync(MentoringBase.metadata.create_all)
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
        session.add(
            UserModel(
                id=OTHER_PROMOTOR_UUID,
                email=OTHER_PROMOTOR_EMAIL,
                role="promotor",
                hashed_password=_hash(OTHER_PROMOTOR_PASSWORD),
            )
        )
        await session.commit()
        yield session
    await engine.dispose()


async def _noop_rate_limit() -> None:
    """No-op rate limiter for tests."""


@pytest.fixture
def client(db_session: AsyncSession) -> Generator[TestClient, None, None]:
    """TestClient with the DB session dependency pointing to in-memory SQLite."""

    async def _override() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override
    app.dependency_overrides[login_rate_limit] = _noop_rate_limit
    tc = TestClient(app, raise_server_exceptions=True)
    yield tc
    app.dependency_overrides.pop(get_db_session, None)
    app.dependency_overrides.pop(login_rate_limit, None)


def login(client: TestClient, email: str, password: str) -> dict[str, str]:
    """Log in and return an Authorization header for that user."""
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token: str = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
