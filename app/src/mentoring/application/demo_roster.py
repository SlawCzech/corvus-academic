"""Demo students: a ready-made roster for someone trying Corvus out.

The same seven fictional students `scripts/seed_demo.py` gives a promoter
from the command line (see `docs/specs/demo-fixtures.md`), here behind a
button: a tester starts from theses with planted defects instead of hunting
for a PDF. Everything goes through the mentoring services, so the result is
what the UI itself would have produced — uploads extracted, versions
numbered, files stored.

Reading the fixtures from disk is the infrastructure's job
(`infrastructure/demo_fixtures.py`); this module only knows what a demo
student is and how to put one on a roster.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from src.mentoring.application.draft_service import DraftService
from src.mentoring.application.guidelines_port import GuidelineSource
from src.mentoring.application.student_service import Caller, StudentService
from src.mentoring.domain.student import ThesisType


@dataclass(frozen=True)
class DemoEvent:
    """One step in a student's history: a meeting note, an uploaded version,
    or the promoter accepting the latest version as final."""

    at: datetime
    note: str | None = None
    draft: Path | None = None
    accepted: bool = False


@dataclass(frozen=True)
class DemoStudent:
    full_name: str
    index_number: str
    field_of_study: str
    thesis_type: ThesisType
    topic: str | None
    timeline: tuple[DemoEvent, ...]


@dataclass
class SeededStudent:
    full_name: str
    notes: int
    versions: int
    guidelines: bool


@dataclass
class DemoSeedReport:
    created: list[SeededStudent] = field(default_factory=lambda: [])
    # Already on the roster by name — left as they are.
    skipped: list[str] = field(default_factory=lambda: [])


class DemoRoster:
    """Puts the demo students on the caller's roster, once each."""

    def __init__(
        self,
        students: StudentService,
        drafts: DraftService,
        guidelines: GuidelineSource,
    ) -> None:
        self._students = students
        self._drafts = drafts
        self._guidelines = guidelines

    async def seed(self, caller: Caller, demo: list[DemoStudent]) -> DemoSeedReport:
        """Create the demo students that are not on the caller's roster yet.

        Safe to repeat: a name already on the roster is skipped, so a tester
        who deleted two of the seven gets exactly those two back.
        """
        report = DemoSeedReport()
        on_roster = {s.full_name for s in await self._students.list_students(caller)}
        for seed_student in demo:
            if seed_student.full_name in on_roster:
                report.skipped.append(seed_student.full_name)
                continue
            report.created.append(await self._create(caller, seed_student))
        return report

    async def _create(self, caller: Caller, seed: DemoStudent) -> SeededStudent:
        started = min(e.at for e in seed.timeline)
        student = await self._students.create(
            caller,
            seed.full_name,
            seed.field_of_study,
            seed.thesis_type,
            seed.index_number,
            created_at=started,
        )
        set_id = await self._guidelines.first_set_for(str(seed.thesis_type))
        await self._students.update(
            caller,
            student.id,
            current_topic=seed.topic,
            topic_set_at=started,
            guideline_set_id=set_id,
            set_guidelines=set_id is not None,
        )

        notes = versions = 0
        latest_draft: uuid.UUID | None = None
        for event in seed.timeline:
            if event.note is not None:
                await self._students.add_meeting_note(
                    caller, student.id, event.note, occurred_at=event.at
                )
                notes += 1
            if event.draft is not None:
                view = await self._drafts.upload(
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
                    raise ValueError(f"{seed.full_name}: 'accepted' before any version")
                await self._drafts.accept(caller, student.id, latest_draft, at=event.at)
        return SeededStudent(
            full_name=seed.full_name,
            notes=notes,
            versions=versions,
            guidelines=set_id is not None,
        )
