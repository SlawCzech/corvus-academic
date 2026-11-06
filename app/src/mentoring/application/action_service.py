"""Use cases for running AI actions against a student.

`app` owns the whole lifecycle around the model call: it decides what the
agent may see (context assembly), records the attempt before dispatching it,
and applies whatever the promoter accepts back onto the student. The agent
only runs the graph.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

import structlog

from src.mentoring.application.agent_client import (
    BYOK,
    AgentClient,
    AgentUnavailableError,
    KeyLoader,
)
from src.mentoring.application.context import (
    assemble_check_progress_context,
    assemble_defence_questions_context,
    assemble_draft_meeting_note_context,
    assemble_draft_student_email_context,
    assemble_evaluate_methodology_context,
    assemble_generate_review_context,
    assemble_propose_topic_context,
    assemble_review_fragment_context,
    assemble_verify_bibliography_context,
    notes_between_versions,
    pseudonymize_context,
)
from src.mentoring.application.draft_service import to_domain as draft_to_domain
from src.mentoring.application.exceptions import (
    ActionNotFoundError,
    FragmentNotFoundError,
    OneOffReviewError,
    ProviderKeyMissingError,
    ProviderRequiredError,
    UnsupportedActionError,
)
from src.mentoring.application.fragment_service import (
    fragment_to_domain,
    part_to_domain,
)
from src.mentoring.application.guidelines_port import (
    GuidelineRubric,
    GuidelineSource,
)
from src.mentoring.application.student_service import (
    Caller,
    StudentService,
)
from src.mentoring.domain.action import (
    ONE_OFF_ACTIONS,
    REVIEW_ACTIONS,
    ActionStatus,
    ActionType,
    AgentAction,
)
from src.mentoring.domain.draft import ThesisDraft
from src.mentoring.domain.fragment import latest_rounds, part_state
from src.mentoring.domain.student import Student
from src.mentoring.infrastructure.orm import AgentActionModel
from src.mentoring.infrastructure.repositories import (
    AgentActionRepository,
    ThesisDraftRepository,
    ThesisFragmentRepository,
    ThesisPartRepository,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _key_for(provider: str | None, keys: KeyLoader | None) -> BYOK:
    """The key a run on `provider` needs. Every run needs one (ADR 0022)."""
    if provider is None:
        raise ProviderRequiredError
    byok = await keys(provider) if keys is not None else None
    if byok is None:
        raise ProviderKeyMissingError(provider)
    return byok


def _usage(model: AgentActionModel) -> dict[str, Any] | None:
    stored: Any = model.usage
    return cast(dict[str, Any], stored) if isinstance(stored, dict) else None


def _to_domain(model: AgentActionModel) -> AgentAction:
    stored: Any = model.output
    output = cast(dict[str, Any], stored) if isinstance(stored, dict) else None
    return AgentAction(
        id=model.id,
        student_id=model.student_id,
        promotor_id=model.promotor_id,
        action_type=ActionType(model.action_type),
        status=ActionStatus(model.status),
        task_id=model.task_id,
        detail=model.detail,
        output=output,
        error=model.error,
        error_code=model.error_code,
        provider=model.provider,
        usage=_usage(model),
        accepted=model.accepted,
        accepted_at=model.accepted_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


@dataclass(frozen=True)
class ActionInProgress:
    """An unfinished action, with the name of the student it is for."""

    action: AgentAction
    student_name: str


class ActionService:
    """Triggers AI actions, tracks them, and applies accepted results."""

    def __init__(
        self,
        students: StudentService,
        actions: AgentActionRepository,
        drafts: ThesisDraftRepository,
        agent: AgentClient,
        guidelines: GuidelineSource | None = None,
        parts: ThesisPartRepository | None = None,
        fragments: ThesisFragmentRepository | None = None,
    ) -> None:
        self._students = students
        self._actions = actions
        self._drafts = drafts
        self._agent = agent
        self._guidelines = guidelines
        self._parts = parts
        self._fragments = fragments

    # ---------- trigger ----------

    async def trigger(
        self,
        caller: Caller,
        student_id: UUID,
        action_type: ActionType,
        token: str,
        detail: str | None = None,
        language: str = "pl",
        review_tone: str = "auto",
        provider: str | None = None,
        keys: KeyLoader | None = None,
        review_findings_first: bool = False,
        fragment_id: UUID | None = None,
    ) -> AgentAction:
        """Record and dispatch one action for a student the caller can see.

        `provider` is whose account the run goes on: one of the providers the
        promoter has a key for. The key is
        fetched through `keys`, forwarded, and never written to the action
        row — the row keeps only the provider's name, which is what a resume
        needs and what the promoter can read back later.

        `review_findings_first` pauses a review after its analyses, for the
        promoter to pick the findings the review may use (see `resume`).

        `fragment_id` is what a `review_fragment` runs on; the fragment then
        points at this run, the latest of any before it.

        Raises ProviderRequiredError without a provider, ProviderKeyMissingError
        when `provider` names a provider the promoter has no key for, and
        OneOffReviewError for an action a one-off review does not take.
        """
        student = await self._students.get(caller, student_id)
        if student.is_one_off and action_type not in ONE_OFF_ACTIONS:
            raise OneOffReviewError(f"A one-off review does not take {action_type}")
        # Before anything is recorded: a run nobody can pay for is a bad
        # request, not a failed action in the student's history.
        byok = await _key_for(provider, keys)
        context, input_ref = await self._assemble(
            caller, student, action_type, detail, review_tone, fragment_id
        )
        # The one way out to a provider, so the one place names come out.
        context = pseudonymize_context(student, context)
        if review_findings_first and action_type in REVIEW_ACTIONS:
            context["promoter_reviews_findings"] = True

        now = datetime.now(UTC)
        record = AgentActionModel(
            id=uuid.uuid4(),
            student_id=student.id,
            promotor_id=caller.user_id,
            action_type=str(action_type),
            status=str(ActionStatus.PENDING),
            detail=detail,
            provider=byok.provider,
            # IDs only: the context itself is reproducible from these rows,
            # and the prompt can be large.
            input_ref=input_ref,
            created_at=now,
            updated_at=now,
        )
        await self._actions.save(record)
        if action_type is ActionType.REVIEW_FRAGMENT:
            await self._point_fragment_at(record)

        try:
            task_id = await self._agent.submit_action(
                action_id=record.id,
                action_type=str(action_type),
                student_id=student.id,
                context=context,
                token=token,
                language=language,
                byok=byok,
            )
        except AgentUnavailableError as exc:
            # The attempt stays on the record — a promoter who clicked and got
            # nothing should see why, not an empty history.
            record.status = str(ActionStatus.FAILED)
            record.error = str(exc)
            await self._actions.update(record)
            logger.error(
                "action_dispatch_failed",
                action_id=str(record.id),
                action_type=str(action_type),
                error=str(exc),
            )
            raise

        record.task_id = task_id
        await self._actions.update(record)
        logger.info(
            "action_dispatched",
            action_id=str(record.id),
            action_type=str(action_type),
            task_id=task_id,
            student_id=str(student.id),
            # Which account pays for this run; never the key itself.
            byok_provider=byok.provider,
        )
        return _to_domain(record)

    # ---------- read ----------

    async def list_actions(
        self,
        caller: Caller,
        student_id: UUID,
        token: str,
        action_type: ActionType | None = None,
    ) -> list[AgentAction]:
        """Return a student's action history, newest first.

        Unfinished actions are refreshed from the agent on the way out. The
        single-action poll is not enough on its own: a client that reloads
        the page loses the id it was polling and only ever asks for the
        list, so without this the row would stay `running` forever while
        the agent's result sits unread.
        """
        student = await self._students.get(caller, student_id)
        records = await self._actions.find_by_student(
            student.id, action_type=str(action_type) if action_type else None
        )
        return [
            await self._refresh(r, token)
            if r.task_id is not None and not ActionStatus(r.status).is_terminal
            else _to_domain(r)
            for r in records
        ]

    async def get_action(
        self,
        caller: Caller,
        student_id: UUID,
        action_id: UUID,
        token: str,
    ) -> AgentAction:
        """Return one action, refreshed from the agent if still running."""
        record = await self._require_record(caller, student_id, action_id)
        action = _to_domain(record)
        if action.is_finished or record.task_id is None:
            return action
        return await self._refresh(record, token)

    async def in_progress(self, caller: Caller, token: str) -> list[ActionInProgress]:
        """Every action of the caller's that is not over yet.

        Pending, running, or paused until the promoter answers.

        Each is checked with the agent first, so one that finished while
        nobody was looking drops off the list instead of padding the count.
        What is left is really running — or dead, for the promoter to cancel.
        Oldest first: the longer it has been going, the likelier it is dead.
        """
        students = await self._students.list_students(caller)
        names = {s.id: s.full_name for s in students}
        records = await self._actions.find_unfinished_by_promotor(caller.user_id)

        unfinished: list[ActionInProgress] = []
        for record in records:
            action = (
                await self._refresh(record, token)
                if record.task_id is not None
                else _to_domain(record)
            )
            if not action.is_finished:
                unfinished.append(
                    ActionInProgress(action, names.get(action.student_id, "—"))
                )
        return unfinished

    # ---------- cancel ----------

    async def cancel(
        self,
        caller: Caller,
        student_id: UUID,
        action_id: UUID,
        token: str,
    ) -> AgentAction:
        """Stop an action that has not finished.

        Our row is marked whatever the agent says: the promoter may be
        clearing a run that died long ago, which the agent may not know about
        or may not be up to hear of. When the agent is reachable it stops the
        run too; when it is not, the run finishes into a row nobody reads.

        Raises ValueError for an action that has already finished.
        """
        record = await self._require_record(caller, student_id, action_id)
        action = _to_domain(record)
        action.cancel()

        if record.task_id is not None:
            try:
                await self._agent.cancel_action(record.task_id, token)
            except AgentUnavailableError as exc:
                logger.warning(
                    "action_cancel_not_forwarded",
                    action_id=str(record.id),
                    error=str(exc),
                )

        record.status = str(action.status)
        await self._actions.update(record)
        logger.info("action_cancelled", action_id=str(record.id))
        return _to_domain(record)

    # ---------- resume ----------

    async def resume(
        self,
        caller: Caller,
        student_id: UUID,
        action_id: UUID,
        accepted_findings: list[int],
        token: str,
        keys: KeyLoader | None = None,
    ) -> AgentAction:
        """Continue a review paused for the promoter, with the findings they kept.

        `accepted_findings` are indices into the findings the paused action
        returned. The run continues on the provider it started on: that key
        is decrypted again for this call — it was never stored with the
        paused run.

        Raises ValueError for an action that is not waiting for a decision,
        ProviderKeyMissingError when the key it started on is gone, and
        ProviderRequiredError for a run started on a local model.
        """
        record = await self._require_record(caller, student_id, action_id)
        action = _to_domain(record)
        action.resume()
        if record.task_id is None:  # pragma: no cover — a paused run has one
            raise ValueError("Action has no run to resume")
        byok = await _key_for(record.provider, keys)

        await self._agent.resume_action(
            record.task_id,
            {"accepted": sorted(set(accepted_findings))},
            token,
            byok=byok,
        )
        record.status = str(action.status)
        await self._actions.update(record)
        logger.info(
            "action_resumed",
            action_id=str(record.id),
            accepted=len(set(accepted_findings)),
        )
        return _to_domain(record)

    # ---------- delete ----------

    async def delete(
        self,
        caller: Caller,
        student_id: UUID,
        action_id: UUID,
        token: str,
    ) -> None:
        """Delete an action from the history, here and in the agent.

        Unlike cancelling, nothing is left behind: the row, its result, and
        the agent's copy of it. One still running is stopped by the agent as
        part of forgetting it. The agent goes first, so a failure there
        (AgentUnavailableError) leaves the action as it was — retrying is
        safe, the agent's side is idempotent.
        """
        record = await self._require_record(caller, student_id, action_id)
        if record.task_id is not None:
            await self._agent.delete_action(record.task_id, token)
        await self._actions.delete(record)
        logger.info("action_deleted", action_id=str(action_id))

    # ---------- accept ----------

    async def accept(
        self,
        caller: Caller,
        student_id: UUID,
        action_id: UUID,
        topic_index: int = 0,
    ) -> AgentAction:
        """Accept a completed action and apply its effect on the student.

        Accepting a topic proposal is what sets `Student.current_topic` — the
        model proposes, the promoter decides, and only the decision is
        denormalized onto the student.
        """
        record = await self._require_record(caller, student_id, action_id)
        action = _to_domain(record)

        # Validate everything before writing anything: an out-of-range index
        # must not leave a half-accepted action behind.
        action.accept()
        await self._apply_effect(caller, action, student_id, topic_index)

        record.accepted = action.accepted
        record.accepted_at = action.accepted_at
        await self._actions.update(record)
        logger.info(
            "action_accepted",
            action_id=str(record.id),
            action_type=record.action_type,
            student_id=str(student_id),
        )
        return _to_domain(record)

    async def mark_used(
        self, caller: Caller, student_id: UUID, action_id: UUID
    ) -> None:
        """Record that the promoter worked from this run's result.

        Accepting with nothing to apply. Saving feedback twice, or from a run
        still in progress, is not an error: there is just nothing to mark.
        """
        record = await self._require_record(caller, student_id, action_id)
        action = _to_domain(record)
        if action.can_be_accepted:
            action.accept()
            record.accepted = action.accepted
            record.accepted_at = action.accepted_at
            await self._actions.update(record)

    async def runs_on_fragment(self, student_id: UUID, fragment_id: UUID) -> list[UUID]:
        """Every `review_fragment` run on a fragment, whatever became of it."""
        records = await self._actions.find_by_student(
            student_id, action_type=str(ActionType.REVIEW_FRAGMENT)
        )
        return [
            r.id
            for r in records
            if cast(dict[str, str], r.input_ref or {}).get("fragment_id")
            == str(fragment_id)
        ]

    # ---------- internals ----------

    async def _assemble(
        self,
        caller: Caller,
        student: Student,
        action_type: ActionType,
        detail: str | None,
        review_tone: str = "auto",
        fragment_id: UUID | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Gather what this action needs, and the provenance of what was used.

        Each action fetches only its own inputs — a progress check reads two
        draft rows, a topic proposal reads none. The returned ``input_ref``
        holds IDs only: the context is reproducible from those rows, and a
        thesis is far too large to log twice.
        """
        base_ref: dict[str, Any] = {"student_id": str(student.id)}

        match action_type:
            case ActionType.PROPOSE_TOPIC:
                notes = await self._students.list_meeting_notes(caller, student.id)
                return (
                    assemble_propose_topic_context(student, notes, detail),
                    base_ref | {"note_ids": [str(n.id) for n in notes]},
                )
            case ActionType.DRAFT_MEETING_NOTE:
                notes = await self._students.list_meeting_notes(caller, student.id)
                return (
                    assemble_draft_meeting_note_context(student, notes, detail),
                    base_ref | {"note_ids": [str(n.id) for n in notes]},
                )
            case ActionType.DRAFT_STUDENT_EMAIL:
                trial = await self._latest_trial_review(student.id)
                return (
                    assemble_draft_student_email_context(student, trial, detail),
                    base_ref | {"trial_review_id": str(trial.id) if trial else None},
                )
            case ActionType.EVALUATE_METHODOLOGY:
                latest = await self._latest_drafts(student.id, 1)
                rubric = await self._rubric(student)
                return (
                    assemble_evaluate_methodology_context(
                        student,
                        latest[0] if latest else None,
                        detail,
                        guidelines=rubric.rubric_md if rubric else None,
                    ),
                    base_ref | self._draft_ref(latest[:1]) | self._rubric_ref(rubric),
                )
            case ActionType.DEFENCE_QUESTIONS:
                latest = await self._latest_drafts(student.id, 1)
                return (
                    assemble_defence_questions_context(
                        student, latest[0] if latest else None, detail
                    ),
                    base_ref | self._draft_ref(latest[:1]),
                )
            case ActionType.GENERATE_REVIEW | ActionType.TRIAL_REVIEW:
                latest = (
                    await self._final_draft(student)
                    if action_type is ActionType.GENERATE_REVIEW
                    else await self._latest_drafts(student.id, 1)
                )
                rubric = await self._rubric(student)
                return (
                    assemble_generate_review_context(
                        student,
                        latest[0] if latest else None,
                        detail,
                        review_tone,
                        guidelines=rubric.rubric_md if rubric else None,
                        thresholds=rubric.thresholds if rubric else None,
                    ),
                    base_ref | self._draft_ref(latest[:1]) | self._rubric_ref(rubric),
                )
            case ActionType.VERIFY_BIBLIOGRAPHY:
                latest = await self._latest_drafts(student.id, 1)
                return (
                    assemble_verify_bibliography_context(
                        student, latest[0] if latest else None
                    ),
                    base_ref | self._draft_ref(latest[:1]),
                )
            case ActionType.CHECK_PROGRESS:
                latest = await self._latest_drafts(student.id, 2)
                notes = notes_between_versions(
                    await self._students.list_meeting_notes(caller, student.id), latest
                )
                return (
                    assemble_check_progress_context(student, latest, notes, detail),
                    base_ref
                    | self._draft_ref(latest)
                    | {"note_ids": [str(n.id) for n in notes]},
                )
            case ActionType.REVIEW_FRAGMENT:
                return await self._assemble_fragment(
                    caller, student, fragment_id, detail, base_ref
                )
            case _:  # pragma: no cover — every ActionType is handled above
                raise UnsupportedActionError(
                    f"No context assembly for action type: {action_type}"
                )

    async def _assemble_fragment(
        self,
        caller: Caller,
        student: Student,
        fragment_id: UUID | None,
        detail: str | None,
        base_ref: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Gather one fragment, the round before it, and what surrounds it."""
        if fragment_id is None or self._parts is None or self._fragments is None:
            raise UnsupportedActionError("review_fragment needs a fragment_id")
        models = await self._fragments.find_by_student(student.id)
        fragments = [fragment_to_domain(m) for m in models]
        fragment = next((f for f in fragments if f.id == fragment_id), None)
        if fragment is None:
            raise FragmentNotFoundError(str(fragment_id))

        parts = [
            part_to_domain(m) for m in await self._parts.find_by_student(student.id)
        ]
        part = next(p for p in parts if p.id == fragment.part_id)
        earlier = [
            f
            for f in fragments
            if f.part_id == part.id and f.round_number < fragment.round_number
        ]
        previous = max(earlier, key=lambda f: f.round_number, default=None)
        latest = latest_rounds(fragments)
        other_parts = [
            (p, part_state(latest.get(p.id))) for p in parts if p.id != part.id
        ]
        notes = await self._students.list_meeting_notes(caller, student.id)
        return (
            assemble_review_fragment_context(
                student, part, fragment, previous, other_parts, notes, detail
            ),
            base_ref | {"fragment_id": str(fragment.id), "part_id": str(part.id)},
        )

    async def _latest_trial_review(self, student_id: UUID) -> AgentAction | None:
        """The newest trial review that finished; the list comes newest first."""
        records = await self._actions.find_by_student(
            student_id, action_type=str(ActionType.TRIAL_REVIEW)
        )
        finished = (_to_domain(r) for r in records)
        return next((a for a in finished if a.status is ActionStatus.COMPLETED), None)

    async def _point_fragment_at(self, record: AgentActionModel) -> None:
        """Make this run the one the fragment shows."""
        ref = cast(dict[str, str], record.input_ref)
        if self._fragments is None:  # pragma: no cover — checked in _assemble
            return
        fragment = await self._fragments.find_by_id(UUID(ref["fragment_id"]))
        if fragment is not None:
            fragment.review_action_id = record.id
            await self._fragments.update(fragment)

    async def _rubric(self, student: Student) -> GuidelineRubric | None:
        """The rubric in force for the student's chosen guideline set."""
        if student.guideline_set_id is None or self._guidelines is None:
            return None
        return await self._guidelines.current_rubric(student.guideline_set_id)

    @staticmethod
    def _rubric_ref(rubric: GuidelineRubric | None) -> dict[str, Any]:
        """Which guideline version the action was judged against — its audit."""
        return {"guideline_version_id": str(rubric.version_id)} if rubric else {}

    async def _latest_drafts(self, student_id: UUID, limit: int) -> list[ThesisDraft]:
        models = await self._drafts.find_latest(student_id, limit=limit)
        return [draft_to_domain(m) for m in models]

    async def _final_draft(self, student: Student) -> list[ThesisDraft]:
        """What a final review reads: the accepted version, else the newest."""
        if student.accepted_draft_id is not None:
            accepted = await self._drafts.find_by_id(student.accepted_draft_id)
            if accepted is not None and accepted.purged_at is None:
                return [draft_to_domain(accepted)]
        return await self._latest_drafts(student.id, 1)

    @staticmethod
    def _draft_ref(drafts: list[ThesisDraft]) -> dict[str, Any]:
        return {
            "draft_ids": [str(d.id) for d in drafts],
            "draft_versions": [d.version_number for d in drafts],
        }

    async def _apply_effect(
        self,
        caller: Caller,
        action: AgentAction,
        student_id: UUID,
        topic_index: int,
    ) -> None:
        """Write what the promoter accepted back into the student's record.

        Only two actions change anything: a topic proposal settles the topic,
        and a drafted note becomes a real meeting note — carrying
        ``source_action_id``, so an AI-drafted note stays distinguishable
        from one the promoter wrote. The rest are read-only advice.
        """
        if action.action_type is ActionType.PROPOSE_TOPIC:
            title = action.topic_title(topic_index)
            await self._students.update(caller, student_id, current_topic=title)
        elif action.action_type is ActionType.DRAFT_MEETING_NOTE:
            await self._students.add_meeting_note(
                caller,
                student_id,
                content=action.drafted_note(),
                source_action_id=action.id,
            )

    async def _require_record(
        self, caller: Caller, student_id: UUID, action_id: UUID
    ) -> AgentActionModel:
        """Load an action of a student the caller can see, or raise."""
        student = await self._students.get(caller, student_id)
        record = await self._actions.find_by_id(action_id)
        if record is None or record.student_id != student.id:
            raise ActionNotFoundError(str(action_id))
        return record

    async def _refresh(self, record: AgentActionModel, token: str) -> AgentAction:
        """Copy the agent's current view of the task onto our own row."""
        task_id = record.task_id
        if task_id is None:  # pragma: no cover — guarded by the caller
            return _to_domain(record)
        try:
            remote = await self._agent.get_action(task_id, token)
        except AgentUnavailableError as exc:
            # Polling must not fail because the agent restarted; the caller
            # keeps seeing the last known state and can poll again.
            logger.warning(
                "action_refresh_failed", action_id=str(record.id), error=str(exc)
            )
            return _to_domain(record)

        record.status = str(ActionStatus(remote.status))
        if remote.result is not None:
            record.output = remote.result
        if remote.error is not None:
            record.error = remote.error
        if remote.error_code is not None:
            record.error_code = remote.error_code
        if remote.usage is not None:
            record.usage = remote.usage
        await self._actions.update(record)
        action = _to_domain(record)
        if not action.is_finished:
            action.progress = remote.progress
        return action
