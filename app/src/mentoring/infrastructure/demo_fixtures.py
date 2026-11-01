"""The demo students on disk: `scripts/seed_data/theses/*/student.toml`.

Each fixture directory holds a `student.toml` — the student's details, topic
and a dated timeline of meeting notes and uploaded versions — next to the
thesis files it names. The directory ships in the `app` image, so both
`scripts/seed_demo.py` and the "load demo students" button read the same
files.
"""

import tomllib
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from src.mentoring.application.demo_roster import DemoEvent, DemoStudent
from src.mentoring.domain.fragment import FragmentVerdict
from src.mentoring.domain.student import ThesisType

# src/mentoring/infrastructure → app/
FIXTURES = Path(__file__).parents[3] / "scripts" / "seed_data" / "theses"


def shift_days(latest: date, as_of: date) -> int:
    """Whole weeks to move a timeline so `latest` lands 1–7 days before `as_of`."""
    return ((as_of - latest).days - 1) // 7 * 7


def _event(raw: dict[str, Any], directory: Path, shift: int) -> DemoEvent:
    day: date = raw["date"] + timedelta(days=shift)
    at = datetime(day.year, day.month, day.day, 12, tzinfo=UTC)
    draft = directory / raw["draft"] if "draft" in raw else None
    if draft is not None and not draft.is_file():
        raise FileNotFoundError(
            f"{draft} is missing — build it with scripts/build_thesis_docx.py"
        )
    fragment = directory / raw["fragment"] if "fragment" in raw else None
    if fragment is not None and not fragment.is_file():
        raise FileNotFoundError(f"{fragment} is missing")
    verdict = raw.get("verdict")
    due: date | None = raw.get("due")
    return DemoEvent(
        at=at,
        note=raw.get("note"),
        draft=draft,
        accepted=bool(raw.get("accepted", False)),
        fragment=fragment,
        part=raw.get("part"),
        question=raw.get("question"),
        verdict=FragmentVerdict(verdict) if verdict else None,
        feedback=raw.get("feedback"),
        due=due + timedelta(days=shift) if due else None,
    )


def load(
    as_of: date | None = None,
    only: list[str] | None = None,
    root: Path = FIXTURES,
) -> list[DemoStudent]:
    """Read the fixtures; with `as_of`, moved to end in the week before it.

    `only` keeps the named fixture directories. The shift is still worked out
    from all of them, so one student reloaded lands where the rest already are.
    """
    files = [
        (path, tomllib.loads(path.read_text(encoding="utf-8")))
        for path in sorted(root.glob("*/student.toml"))
    ]
    if only:
        unknown = set(only) - {path.parent.name for path, _ in files}
        if unknown:
            raise ValueError(f"No such fixture: {', '.join(sorted(unknown))}")
    shift = 0
    if as_of is not None:
        latest = max(e["date"] for _, raw in files for e in raw["timeline"])
        shift = shift_days(latest, as_of)
    students: list[DemoStudent] = []
    for path, raw in files:
        if only and path.parent.name not in only:
            continue
        students.append(
            DemoStudent(
                full_name=raw["full_name"],
                index_number=raw["index_number"],
                field_of_study=raw["field_of_study"],
                thesis_type=ThesisType(raw["thesis_type"]),
                topic=raw.get("topic"),
                timeline=tuple(_event(e, path.parent, shift) for e in raw["timeline"]),
                research_area=raw.get("research_area"),
                research_aim=raw.get("research_aim"),
            )
        )
    return students
