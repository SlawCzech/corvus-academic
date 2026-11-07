"""Re-encrypt the stored provider keys under a new FERNET_KEY.

`identity.user_api_keys` is the only thing Fernet-encrypted with FERNET_KEY.
Run this after the new key is in `.env` and before `app` restarts on it; the
old key comes in OLD_FERNET_KEY, never on the command line:

    OLD_FERNET_KEY="$(cat .fernet-old)" docker compose -f docker-compose.prod.yml \
        run --rm -e OLD_FERNET_KEY app python scripts/rotate_fernet_key.py
    ... the same with --apply

Without --apply it only reports. All or nothing: a key that neither the old
nor the new FERNET_KEY opens stops the run before anything is written. A key
already under the new FERNET_KEY is left as it is, so a second run is safe.
Nothing here prints a key.
"""

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass, field

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.identity.infrastructure.models import UserApiKeyModel


@dataclass
class Report:
    """What a run found, by row; no key ever lands here."""

    rotated: int = 0
    already_new: int = 0
    unreadable: list[str] = field(default_factory=list[str])


class SameKeyError(ValueError):
    """OLD_FERNET_KEY equals FERNET_KEY — the `.env` was not changed yet."""


async def rotate(
    session: AsyncSession, old_key: str, new_key: str, *, apply: bool
) -> Report:
    """Re-encrypt every stored key from ``old_key`` to ``new_key``.

    Writes (and commits) only with ``apply`` and only when every row could be
    read; otherwise the session is rolled back and the report says why.
    """
    if old_key.strip() == new_key.strip():
        raise SameKeyError("OLD_FERNET_KEY and FERNET_KEY are the same key")
    old, new = Fernet(old_key.encode()), Fernet(new_key.encode())

    report = Report()
    rows = (await session.execute(select(UserApiKeyModel))).scalars().all()
    for row in rows:
        token = row.key_encrypted.encode()
        try:
            new.decrypt(token)
            report.already_new += 1
            continue
        except InvalidToken:
            pass
        try:
            plain = old.decrypt(token)
        except InvalidToken:
            report.unreadable.append(f"{row.user_id}/{row.provider}")
            continue
        row.key_encrypted = new.encrypt(plain).decode()
        report.rotated += 1

    if apply and not report.unreadable:
        await session.commit()
    else:
        await session.rollback()
    return report


async def _main(apply: bool) -> int:
    old_key = os.environ.get("OLD_FERNET_KEY", "")
    if not old_key:
        print("OLD_FERNET_KEY is not set — pass it with `run -e OLD_FERNET_KEY`")
        return 2

    from src.shared.database import session_factory
    from src.shared.settings import settings

    async with session_factory() as session:
        try:
            report = await rotate(session, old_key, settings.fernet_key, apply=apply)
        except SameKeyError as exc:
            print(f"{exc}: put the new FERNET_KEY in .env first")
            return 2

    print(
        f"re-encrypted: {report.rotated}, already under the new key: "
        f"{report.already_new}, unreadable: {len(report.unreadable)}"
    )
    for where in report.unreadable:
        print(f"  unreadable (user/provider): {where}")
    if report.unreadable:
        print(
            "nothing written — an unreadable key means a wrong OLD_FERNET_KEY "
            "or a damaged row; the owner can enter that key again"
        )
        return 1
    print("written" if apply else "dry run — nothing written; add --apply")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Re-encrypt the stored provider keys.")
    parser.add_argument("--apply", action="store_true", help="write the new values")
    sys.exit(asyncio.run(_main(parser.parse_args().apply)))
