"""Fill a promoter's roster with the demo students, their notes and theses.

Seven fictional students from `scripts/seed_data/theses/` — six with a thesis
built to exercise the AI actions (see `docs/specs/demo-fixtures.md` and each
`EXPECTED.md`), one with meeting notes only. Everything goes through the
mentoring services, so the result is exactly what the UI would have produced:
uploads are extracted, versions numbered, files stored.

    python scripts/seed_demo.py --promotor promotor@example.com
    python scripts/seed_demo.py --promotor promotor@example.com --as-of today
    python scripts/seed_demo.py --promotor promotor@example.com --reset
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
deleted.
"""

import argparse
import asyncio
import sys
import tomllib
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.document.extractor import extract
from src.mentoring.domain.student import ThesisType

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.guidelines.application.catalog import GuidelineCatalog
    from src.identity.infrastructure.models import UserModel
    from src.mentoring.application.agent_client import AgentClient

_DATA = Path(__file__).parent / "seed_data" / "theses"


@dataclass(frozen=True)
class _Event:
    """One step in a student's history: a meeting note, an uploaded version,
    or the promoter accepting the latest version as final."""

    at: datetime
    note: str | None = None
    draft: Path | None = None
    accepted: bool = False


@dataclass(frozen=True)
class _SeedStudent:
    full_name: str
    index_number: str
    field_of_study: str
    thesis_type: ThesisType
    topic: str | None
    timeline: tuple[_Event, ...]


def shift_days(latest: date, as_of: date) -> int:
    """Whole weeks to move a timeline so `latest` lands 1–7 days before `as_of`."""
    return ((as_of - latest).days - 1) // 7 * 7


def _event(raw: dict[str, Any], directory: Path, shift: int) -> _Event:
    day: date = raw["date"] + timedelta(days=shift)
    at = datetime(day.year, day.month, day.day, 12, tzinfo=UTC)
    draft = directory / raw["draft"] if "draft" in raw else None
    if draft is not None and not draft.is_file():
        raise FileNotFoundError(
            f"{draft} is missing — build it with scripts/build_thesis_docx.py"
        )
    return _Event(
        at=at,
        note=raw.get("note"),
        draft=draft,
        accepted=bool(raw.get("accepted", False)),
    )


def load(as_of: date | None = None) -> list[_SeedStudent]:
    """Read every fixture; with `as_of`, moved to end in the week before it."""
    files = [
        (path, tomllib.loads(path.read_text(encoding="utf-8")))
        for path in sorted(_DATA.glob("*/student.toml"))
    ]
    shift = 0
    if as_of is not None:
        latest = max(e["date"] for _, raw in files for e in raw["timeline"])
        shift = shift_days(latest, as_of)
    students: list[_SeedStudent] = []
    for path, raw in files:
        students.append(
            _SeedStudent(
                full_name=raw["full_name"],
                index_number=raw["index_number"],
                field_of_study=raw["field_of_study"],
                thesis_type=ThesisType(raw["thesis_type"]),
                topic=raw.get("topic"),
                timeline=tuple(
                    _event(e, path.parent, shift) for e in raw["timeline"]
                ),
            )
        )
    return students


def dry_run(students: list[_SeedStudent]) -> None:
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


async def _guideline_set(
    catalog: "GuidelineCatalog", thesis_type: ThesisType
) -> uuid.UUID | None:
    """The first set with a published version for this kind of thesis."""
    summaries = await catalog.list_sets(str(thesis_type))
    return summaries[0].guideline_set.id if summaries else None


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
    students: list[_SeedStudent],
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
    session: "AsyncSession", promotor_email: str, students: list[_SeedStudent]
) -> int:
    """Create the students that are not on the promoter's roster yet."""
    from src.guidelines.application.catalog import GuidelineCatalog
    from src.guidelines.infrastructure.orm import SourceFileModel
    from src.guidelines.infrastructure.repositories import CatalogRepository
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
    caller = Caller(user_id=user.id)

    catalog = GuidelineCatalog(
        CatalogRepository(session), SqlFileStore(session, SourceFileModel)
    )
    service = StudentService(
        StudentRepository(session),
        MeetingNoteRepository(session),
        CatalogGuidelineSource(catalog),
    )
    drafts = DraftService(
        service,
        ThesisDraftRepository(session),
        SqlFileStore(session, DraftFileModel),
    )

    on_roster = {s.full_name for s in await service.list_students(caller)}
    for seed_student in students:
        if seed_student.full_name in on_roster:
            print(f"{seed_student.full_name}: already on the roster — skipping")
            continue

        started = min(e.at for e in seed_student.timeline)
        student = await service.create(
            caller,
            seed_student.full_name,
            seed_student.field_of_study,
            seed_student.thesis_type,
            seed_student.index_number,
            created_at=started,
        )
        set_id = await _guideline_set(catalog, seed_student.thesis_type)
        if set_id is None:
            print(
                f"  no published guidelines for {seed_student.thesis_type} "
                f"theses — run seed_guidelines.py to have reviews use them"
            )
        await service.update(
            caller,
            student.id,
            current_topic=seed_student.topic,
            topic_set_at=started,
            guideline_set_id=set_id,
            set_guidelines=set_id is not None,
        )

        notes = versions = 0
        latest_draft: uuid.UUID | None = None
        for event in seed_student.timeline:
            if event.note is not None:
                await service.add_meeting_note(
                    caller, student.id, event.note, occurred_at=event.at
                )
                notes += 1
            if event.draft is not None:
                view = await drafts.upload(
                    caller,
                    student.id,
                    event.draft.name,
                    event.draft.read_bytes(),
                    uploaded_at=event.at,
                )
                latest_draft = view.draft.id
                versions += 1
            if event.accepted:
                if latest_draft is None:
                    raise ValueError(
                        f"{seed_student.full_name}: 'accepted' before any version"
                    )
                await drafts.accept(caller, student.id, latest_draft, at=event.at)
        print(
            f"{seed_student.full_name}: created with {notes} note(s) "
            f"and {versions} thesis version(s)"
        )
    return 0


async def seed(promotor_email: str, students: list[_SeedStudent], reset: bool) -> int:
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
        "--as-of",
        type=_day,
        metavar="YYYY-MM-DD|today",
        help="move the timeline to end in the week before this day",
    )
    args = parser.parse_args()
    students = load(args.as_of)
    if args.dry_run:
        dry_run(students)
        return 0
    if not args.promotor:
        parser.error("--promotor is required (or use --dry-run)")
    return asyncio.run(seed(args.promotor, students, args.reset))


if __name__ == "__main__":
    sys.exit(main())
