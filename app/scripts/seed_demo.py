"""Fill a promoter's roster with the demo students, their notes and theses.

Seven fictional students from `scripts/seed_data/theses/` — six with a thesis
built to exercise the AI actions (see `docs/specs/demo-fixtures.md` and each
`EXPECTED.md`), one with meeting notes only. Everything goes through the
mentoring services, so the result is exactly what the UI would have produced:
uploads are extracted, versions numbered, files stored.

    python scripts/seed_demo.py --promotor promotor@example.com
    python scripts/seed_demo.py --promotor promotor@example.com --as-of today
    python scripts/seed_demo.py --promotor promotor@example.com --reset
    python scripts/seed_demo.py --promotor p@example.com --reset --only 06_adamczewski
    python scripts/seed_demo.py --dry-run

Everything is dated as its `student.toml` says — the student from the first
entry of the timeline, each note and version from its own — so the roster
reads as a year of supervision, not as seven students added this minute.
`--as-of` moves the whole timeline by whole weeks (weekdays and gaps stay) so
that its last entry falls in the week before that day. Off by default: the
theses name their own dates ("ankietę przeprowadzono w listopadzie 2025 r."),
and a moved timeline no longer agrees with them.

The promoter account must already exist — an admin creates it; an admin cannot
hold students (ADR 0008). A student whose name is already on that promoter's
roster is left alone, so the script is safe to run again. `--dry-run` touches
no database: it reads the data and extracts every thesis file.

`--reset` first deletes the demo students from that roster — the seven named
in the fixtures, nobody else — with their notes, versions, files and AI
results, the way the promoter's own "delete student" does (ADR 0009), and
then seeds them again. It needs the agent running; without it nothing is
deleted. `--only` narrows either to the named fixture directories: one thesis
changed, and the results already run for the other students should stay.

The seeding itself is `DemoRoster` — the same code behind the "load demo
students" button on an empty roster; this script adds the command line,
`--reset` and `--as-of`.
"""

import argparse
import asyncio
import sys
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from src.document.extractor import extract
from src.mentoring.application.demo_roster import DemoStudent
from src.mentoring.infrastructure.demo_fixtures import load, shift_days

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.identity.infrastructure.models import UserModel
    from src.mentoring.application.agent_client import AgentClient

__all__ = ["load", "reset_roster", "seed_roster", "shift_days"]


def dry_run(students: list[DemoStudent]) -> None:
    for student in students:
        notes = sum(1 for e in student.timeline if e.note)
        print(f"{student.full_name} ({student.thesis_type}): {notes} note(s)")
        for event in student.timeline:
            day = event.at.date().isoformat()
            if event.note is not None:
                print(f"  {day}  note")
            if event.draft is not None:
                document = extract(event.draft.read_bytes(), event.draft.name)
                print(f"  {day}  {event.draft.name}: {len(document.text)} chars")
            if event.accepted:
                print(f"  {day}  latest version accepted as final")


async def _promoter(session: "AsyncSession", email: str) -> "UserModel | None":
    """The promoter account the students belong to, or None with the reason."""
    # Imported here, not at the top: these read the settings (database URL,
    # secrets) on import, and `--dry-run` must work without any of them.
    from sqlalchemy import select

    from src.identity.infrastructure.models import UserModel

    user = (
        await session.execute(select(UserModel).where(UserModel.email == email))
    ).scalar_one_or_none()
    if user is None:
        print(f"No user {email!r} — create the promoter account first")
        return None
    if user.role != "promotor":
        print(f"{email!r} is {user.role!r}; students need a promoter")
        return None
    return user


async def reset_roster(
    session: "AsyncSession",
    promotor_email: str,
    students: list[DemoStudent],
    agent: "AgentClient",
) -> int:
    """Delete the demo students from the promoter's roster — and only those."""
    from src.identity.application.auth import create_access_token
    from src.identity.domain.user import Role, User
    from src.mentoring.application.exceptions import AgentUnavailableError
    from src.mentoring.application.student_deletion import StudentDeletionService
    from src.mentoring.application.student_service import Caller, StudentService
    from src.mentoring.infrastructure.orm import DraftFileModel
    from src.mentoring.infrastructure.repositories import (
        MeetingNoteRepository,
        StudentRepository,
        ThesisDraftRepository,
    )
    from src.shared.sql_file_store import SqlFileStore

    user = await _promoter(session, promotor_email)
    if user is None:
        return 1
    caller = Caller(user_id=user.id)
    # The agent takes the promoter's own token for its copies of the results;
    # the script acts as that promoter, so it signs one for them.
    token = create_access_token(
        User(
            id=user.id,
            email=user.email,
            role=Role(user.role),
            created_at=user.created_at,
        )
    )
    service = StudentService(StudentRepository(session), MeetingNoteRepository(session))
    deletion = StudentDeletionService(
        service,
        StudentRepository(session),
        ThesisDraftRepository(session),
        SqlFileStore(session, DraftFileModel),
        agent,
    )

    demo_names = {s.full_name for s in students}
    for student in await service.list_students(caller):
        if student.full_name not in demo_names:
            continue
        try:
            await deletion.delete(caller, student.id, token)
        except AgentUnavailableError as exc:
            print(f"{student.full_name}: not deleted — agent unavailable ({exc})")
            return 1
        print(f"{student.full_name}: deleted")
    return 0


async def seed_roster(
    session: "AsyncSession", promotor_email: str, students: list[DemoStudent]
) -> int:
    """Create the students that are not on the promoter's roster yet."""
    from src.guidelines.application.catalog import GuidelineCatalog
    from src.guidelines.infrastructure.orm import SourceFileModel
    from src.guidelines.infrastructure.repositories import CatalogRepository
    from src.mentoring.application.demo_roster import DemoRoster
    from src.mentoring.application.draft_service import DraftService
    from src.mentoring.application.student_service import Caller, StudentService
    from src.mentoring.infrastructure.guidelines_adapter import (
        CatalogGuidelineSource,
    )
    from src.mentoring.infrastructure.orm import DraftFileModel
    from src.mentoring.infrastructure.repositories import (
        MeetingNoteRepository,
        StudentRepository,
        ThesisDraftRepository,
    )
    from src.shared.sql_file_store import SqlFileStore

    user = await _promoter(session, promotor_email)
    if user is None:
        return 1

    guidelines = CatalogGuidelineSource(
        GuidelineCatalog(
            CatalogRepository(session), SqlFileStore(session, SourceFileModel)
        )
    )
    service = StudentService(
        StudentRepository(session), MeetingNoteRepository(session), guidelines
    )
    drafts = DraftService(
        service,
        ThesisDraftRepository(session),
        SqlFileStore(session, DraftFileModel),
    )
    report = await DemoRoster(service, drafts, guidelines).seed(
        Caller(user_id=user.id), students
    )
    for name in report.skipped:
        print(f"{name}: already on the roster — skipping")
    for seeded in report.created:
        if not seeded.guidelines:
            print(
                f"  {seeded.full_name}: no published guidelines for this kind "
                f"of thesis — run seed_guidelines.py to have reviews use them"
            )
        print(
            f"{seeded.full_name}: created with {seeded.notes} note(s) "
            f"and {seeded.versions} thesis version(s)"
        )
    return 0


async def seed(promotor_email: str, students: list[DemoStudent], reset: bool) -> int:
    import httpx

    from src.mentoring.application.agent_client import AgentClient
    from src.shared.database import session_factory
    from src.shared.settings import settings

    async with session_factory() as session:
        if reset:
            async with httpx.AsyncClient(timeout=30.0) as client:
                agent = AgentClient(client, settings.agent_url)
                if await reset_roster(session, promotor_email, students, agent):
                    return 1
        return await seed_roster(session, promotor_email, students)


def _day(value: str) -> date:
    return datetime.now(UTC).date() if value == "today" else date.fromisoformat(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the demo students.")
    parser.add_argument("--promotor", help="e-mail of the promoter who gets them")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="read the seed data and extract every thesis, without a database",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="delete the demo students from the roster first, then seed them",
    )
    parser.add_argument(
        "--only",
        action="append",
        metavar="FIXTURE",
        help="a fixture directory (e.g. 06_adamczewski); repeat for several",
    )
    parser.add_argument(
        "--as-of",
        type=_day,
        metavar="YYYY-MM-DD|today",
        help="move the timeline to end in the week before this day",
    )
    args = parser.parse_args()
    students = load(args.as_of, args.only)
    if args.dry_run:
        dry_run(students)
        return 0
    if not args.promotor:
        parser.error("--promotor is required (or use --dry-run)")
    return asyncio.run(seed(args.promotor, students, args.reset))


if __name__ == "__main__":
    sys.exit(main())
