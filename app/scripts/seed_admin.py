"""Create the default admin user in identity.users if it does not exist.

Run after `alembic upgrade head`. Safe to run multiple times (idempotent).
Skips silently when ADMIN_PASSWORD is not set.
"""

import asyncio
import sys
import uuid
from datetime import UTC, datetime

import bcrypt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.shared.settings import settings


async def seed() -> None:
    if not settings.admin_password:
        print("ADMIN_PASSWORD not set — skipping admin seed")
        return

    engine = create_async_engine(settings.database_url)
    hashed = bcrypt.hashpw(settings.admin_password.encode(), bcrypt.gensalt()).decode()

    async with engine.begin() as conn:
        row = await conn.execute(
            text("SELECT id FROM identity.users WHERE email = :email"),
            {"email": settings.admin_email},
        )
        if row.fetchone() is not None:
            print(f"Admin {settings.admin_email!r} already exists — skipping")
            await engine.dispose()
            return

        await conn.execute(
            text(
                "INSERT INTO identity.users"
                " (id, email, role, hashed_password, created_at)"
                " VALUES (:id, :email, :role, :hashed_password, :created_at)"
            ),
            {
                "id": str(uuid.uuid4()),
                "email": settings.admin_email,
                "role": "admin",
                "hashed_password": hashed,
                "created_at": datetime.now(UTC),
            },
        )
        print(f"Admin {settings.admin_email!r} created")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
    sys.exit(0)
