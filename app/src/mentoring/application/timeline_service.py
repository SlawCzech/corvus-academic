"""The work timeline: where a student stands, and how they got there.

A derived view, with no table of its own: fragments, meeting notes and whole
versions already say what happened and when (ADR 0014).
"""

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from src.mentoring.application.action_service import ActionService
from src.mentoring.application.draft_service import DraftService, DraftView
from src.mentoring.application.fragment_service import (
    fragment_to_domain,
    part_to_domain,
)
from src.mentoring.application.student_service import Caller, StudentService
from src.mentoring.domain.action import ActionType, AgentAction
from src.mentoring.domain.fragment import (
    PartState,
    ThesisFragment,
    ThesisPart,
    latest_rounds,
    part_state,
)
from src.mentoring.domain.student import MeetingNote
from src.mentoring.infrastructure.repositories import (
    ThesisFragmentRepository,
    ThesisPartRepository,
)


@dataclass(frozen=True)
class PartEntry:
    """A part, and where it stands."""

    part: ThesisPart
    rounds: int
    state: PartState


@dataclass(frozen=True)
class FragmentEntry:
    """A fragment with its part's name and the AI run it points at, if any."""

    fragment: ThesisFragment
    part_name: str
    review: AgentAction | None

    @property
    def summary(self) -> str | None:
        """What the AI said was handed in. Lives in the run, not the fragment."""
        if self.review is None:
            return None
        summary = self.review.structured_output().get("summary")
        return str(summary) if summary else None


@dataclass(frozen=True)
class TimelineEvent:
    """One thing that happened: exactly one of the three is set."""

    on: date
    recorded_at: datetime
    fragment: FragmentEntry | None = None
    note: MeetingNote | None = None
    draft: DraftView | None = None


@dataclass(frozen=True)
class WorkTimeline:
    parts: list[PartEntry]
    events: list[TimelineEvent]


class TimelineService:
    """Composes the "Przebieg pracy" section in one read."""

    def __init__(
        self,
        students: StudentService,
        parts: ThesisPartRepository,
        fragments: ThesisFragmentRepository,
        drafts: DraftService,
        actions: ActionService,
    ) -> None:
        self._students = students
        self._parts = parts
        self._fragments = fragments
        self._drafts = drafts
        self._actions = actions

    async def timeline(
        self, caller: Caller, student_id: UUID, token: str
    ) -> WorkTimeline:
        """Return a student's parts, and everything that happened, newest first.

        Runs are read through `list_actions`, which refreshes unfinished ones
        from the agent: a promoter who left before the summary was ready finds
        it here when they come back.
        """
        student = await self._students.get(caller, student_id)
        parts = [
            part_to_domain(m) for m in await self._parts.find_by_student(student.id)
        ]
        fragments = [
            fragment_to_domain(m)
            for m in await self._fragments.find_by_student(student.id)
        ]
        runs = {
            a.id: a
            for a in await self._actions.list_actions(
                caller, student.id, token, ActionType.REVIEW_FRAGMENT
            )
        }
        names = {p.id: p.name for p in parts}
        latest = latest_rounds(fragments)

        events = [
            TimelineEvent(
                on=f.received_on,
                recorded_at=f.created_at,
                fragment=FragmentEntry(
                    f,
                    names[f.part_id],
                    runs.get(f.review_action_id) if f.review_action_id else None,
                ),
            )
            for f in fragments
        ]
        events += [
            TimelineEvent(on=n.occurred_at.date(), recorded_at=n.created_at, note=n)
            for n in await self._students.list_meeting_notes(caller, student.id)
        ]
        events += [
            TimelineEvent(
                on=d.draft.created_at.date(),
                recorded_at=d.draft.created_at,
                draft=d,
            )
            for d in await self._drafts.list_drafts(caller, student.id)
        ]
        events.sort(key=lambda e: (e.on, e.recorded_at), reverse=True)

        return WorkTimeline(
            parts=[
                PartEntry(
                    part=p,
                    rounds=sum(1 for f in fragments if f.part_id == p.id),
                    state=part_state(latest.get(p.id)),
                )
                for p in parts
            ],
            events=events,
        )
