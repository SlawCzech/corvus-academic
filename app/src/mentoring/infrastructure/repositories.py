"""Async repositories for persisting mentoring data."""

import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.mentoring.domain.model_policy import ModelPolicy, ModelSetting
from src.mentoring.infrastructure.orm import (
    AgentActionModel,
    MeetingNoteModel,
    ModelSettingModel,
    StudentModel,
    ThesisDraftModel,
    ThesisFragmentModel,
    ThesisPartModel,
)


class StudentRepository:
    """Async CRUD operations for student records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, model: StudentModel) -> None:
        """Persist a new student record and commit."""
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)

    async def add(self, model: StudentModel) -> None:
        """Write a new student without committing, for a larger unit of work."""
        self._session.add(model)
        await self._session.flush()

    async def rollback(self) -> None:
        """Drop whatever the unit of work holds."""
        await self._session.rollback()

    async def update(self, model: StudentModel) -> None:
        """Commit in-place changes to an already-persisted student."""
        await self._session.commit()
        await self._session.refresh(model)

    async def find_by_id(self, student_id: uuid.UUID) -> StudentModel | None:
        """Return the student with the given id, or None if not found."""
        return await self._session.get(StudentModel, student_id)

    async def find_all(
        self,
        promotor_id: uuid.UUID | None = None,
        status: str | None = None,
        one_off: bool | None = None,
    ) -> list[StudentModel]:
        """Return students with optional filters, newest first.

        Services always pass ``promotor_id``: a promoter sees only their own
        students (ADR 0008). ``one_off=None`` means both students and one-off
        reviews.
        """
        stmt = select(StudentModel).order_by(StudentModel.created_at.desc())
        if promotor_id is not None:
            stmt = stmt.where(StudentModel.promotor_id == promotor_id)
        if status is not None:
            stmt = stmt.where(StudentModel.status == status)
        if one_off is not None:
            stmt = stmt.where(StudentModel.is_one_off == one_off)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def find_retention_candidates(self) -> list[StudentModel]:
        """Students that could have a version due for purging.

        Only those whose supervision ended or who have an accepted version —
        everyone else has nothing the retention policy could act on.
        """
        result = await self._session.execute(
            select(StudentModel).where(
                or_(
                    StudentModel.closed_at.is_not(None),
                    StudentModel.draft_accepted_at.is_not(None),
                )
            )
        )
        return list(result.scalars().all())

    async def delete(self, student_id: uuid.UUID) -> None:
        """Delete a student and every record of theirs, in one commit.

        Notes, fragments, actions and versions are deleted by statement rather than left
        to ``ON DELETE CASCADE``: the result is the same in Postgres, and it
        does not depend on a database enforcing foreign keys (SQLite, in
        tests, does not). The versions' files are not rows of these tables —
        delete them through the ``FileStore`` first, in the same session, so
        they go in this commit too.
        """
        await self._session.execute(
            delete(MeetingNoteModel).where(MeetingNoteModel.student_id == student_id)
        )
        await self._session.execute(
            delete(ThesisFragmentModel).where(
                ThesisFragmentModel.student_id == student_id
            )
        )
        await self._session.execute(
            delete(ThesisPartModel).where(ThesisPartModel.student_id == student_id)
        )
        await self._session.execute(
            delete(AgentActionModel).where(AgentActionModel.student_id == student_id)
        )
        await self._session.execute(
            delete(ThesisDraftModel).where(ThesisDraftModel.student_id == student_id)
        )
        await self._session.execute(
            delete(StudentModel).where(StudentModel.id == student_id)
        )
        await self._session.commit()


class MeetingNoteRepository:
    """Async store for meeting notes."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, model: MeetingNoteModel) -> None:
        """Persist a meeting note and commit."""
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)

    async def find_by_student(self, student_id: uuid.UUID) -> list[MeetingNoteModel]:
        """Return a student's meeting notes, most recent meeting first."""
        result = await self._session.execute(
            select(MeetingNoteModel)
            .where(MeetingNoteModel.student_id == student_id)
            .order_by(MeetingNoteModel.occurred_at.desc())
        )
        return list(result.scalars().all())


class AgentActionRepository:
    """Async store for the AI action log."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, model: AgentActionModel) -> None:
        """Persist a new action and commit."""
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)

    async def update(self, model: AgentActionModel) -> None:
        """Commit in-place changes to an already-persisted action."""
        await self._session.commit()
        await self._session.refresh(model)

    async def delete(self, model: AgentActionModel) -> None:
        """Delete one action and commit.

        A meeting note written from it, and a fragment reviewed by it, keep
        what they hold and lose only the link — set explicitly, as
        ``ON DELETE SET NULL`` would, so it does not depend on the database
        enforcing foreign keys.
        """
        await self._session.execute(
            update(MeetingNoteModel)
            .where(MeetingNoteModel.source_action_id == model.id)
            .values(source_action_id=None)
        )
        await self._session.execute(
            update(ThesisFragmentModel)
            .where(ThesisFragmentModel.review_action_id == model.id)
            .values(review_action_id=None)
        )
        await self._session.execute(
            update(ThesisFragmentModel)
            .where(ThesisFragmentModel.feedback_source_action_id == model.id)
            .values(feedback_source_action_id=None)
        )
        await self._session.delete(model)
        await self._session.commit()

    async def find_by_id(self, action_id: uuid.UUID) -> AgentActionModel | None:
        """Return the action with the given id, or None if not found."""
        return await self._session.get(AgentActionModel, action_id)

    async def find_by_student(
        self,
        student_id: uuid.UUID,
        action_type: str | None = None,
    ) -> list[AgentActionModel]:
        """Return a student's actions, newest first, optionally by type."""
        stmt = (
            select(AgentActionModel)
            .where(AgentActionModel.student_id == student_id)
            .order_by(AgentActionModel.created_at.desc())
        )
        if action_type is not None:
            stmt = stmt.where(AgentActionModel.action_type == action_type)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def find_recent_by_promotor(
        self,
        promotor_id: uuid.UUID,
        limit: int = 30,
    ) -> list[AgentActionModel]:
        """Return the most recently updated actions across a promoter's students."""
        stmt = (
            select(AgentActionModel)
            .where(AgentActionModel.promotor_id == promotor_id)
            .order_by(AgentActionModel.updated_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def find_unfinished_by_promotor(
        self, promotor_id: uuid.UUID
    ) -> list[AgentActionModel]:
        """Return every action that is not over, oldest first.

        Pending, running — and paused for the promoter: a review waiting for
        their pick of findings is the one unfinished action that needs them.

        No limit: this is the list the promoter clears stale runs from, and
        the oldest are the likeliest to be dead.
        """
        stmt = (
            select(AgentActionModel)
            .where(
                AgentActionModel.promotor_id == promotor_id,
                AgentActionModel.status.in_(("pending", "running", "awaiting_input")),
            )
            .order_by(AgentActionModel.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class ThesisDraftRepository:
    """Async store for uploaded thesis versions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, model: ThesisDraftModel) -> None:
        """Persist a draft version and commit."""
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)

    async def update(self, model: ThesisDraftModel) -> None:
        """Commit in-place changes to an already-persisted version."""
        await self._session.commit()
        await self._session.refresh(model)

    async def commit(self) -> None:
        """Commit whatever the unit of work holds — the retention sweep's batch."""
        await self._session.commit()

    async def find_by_id(self, draft_id: uuid.UUID) -> ThesisDraftModel | None:
        """Return one version, or None."""
        return await self._session.get(ThesisDraftModel, draft_id)

    async def find_by_student(self, student_id: uuid.UUID) -> list[ThesisDraftModel]:
        """Return a student's versions, newest first."""
        result = await self._session.execute(
            select(ThesisDraftModel)
            .where(ThesisDraftModel.student_id == student_id)
            .order_by(ThesisDraftModel.version_number.desc())
        )
        return list(result.scalars().all())

    async def find_latest(
        self, student_id: uuid.UUID, limit: int = 1
    ) -> list[ThesisDraftModel]:
        """Return the newest readable versions, newest first — at most `limit`.

        `check_progress` asks for two; nothing needs the whole history, and a
        thesis text is large enough that loading it all would be wasteful.
        Purged versions are skipped: they have no text to hand to an action.
        """
        result = await self._session.execute(
            select(ThesisDraftModel)
            .where(
                ThesisDraftModel.student_id == student_id,
                ThesisDraftModel.purged_at.is_(None),
            )
            .order_by(ThesisDraftModel.version_number.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def next_version_number(self, student_id: uuid.UUID) -> int:
        """Return the version number the next upload should get."""
        result = await self._session.execute(
            select(func.max(ThesisDraftModel.version_number)).where(
                ThesisDraftModel.student_id == student_id
            )
        )
        current: int | None = result.scalar_one_or_none()
        return (current or 0) + 1


class ThesisPartRepository:
    """Async store for the parts of a thesis."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, model: ThesisPartModel) -> None:
        """Persist a new part and commit."""
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)

    async def commit(self) -> None:
        """Commit in-place changes to parts already persisted."""
        await self._session.commit()

    async def delete(self, model: ThesisPartModel) -> None:
        """Delete one part and commit."""
        await self._session.delete(model)
        await self._session.commit()

    async def find_by_id(self, part_id: uuid.UUID) -> ThesisPartModel | None:
        """Return one part, or None."""
        return await self._session.get(ThesisPartModel, part_id)

    async def find_by_student(self, student_id: uuid.UUID) -> list[ThesisPartModel]:
        """Return a student's parts in the promoter's order."""
        result = await self._session.execute(
            select(ThesisPartModel)
            .where(ThesisPartModel.student_id == student_id)
            .order_by(ThesisPartModel.position)
        )
        return list(result.scalars().all())

    async def find_overdue(
        self, student_ids: Sequence[uuid.UUID], today: date
    ) -> list[ThesisPartModel]:
        """Return parts past their deadline, the longest overdue first.

        A fragment clears a part's deadline, so one still set is still unmet.
        """
        result = await self._session.execute(
            select(ThesisPartModel)
            .where(
                ThesisPartModel.student_id.in_(student_ids),
                ThesisPartModel.due_on < today,
            )
            .order_by(ThesisPartModel.due_on)
        )
        return list(result.scalars().all())

    async def find_by_ids(
        self, part_ids: Sequence[uuid.UUID]
    ) -> list[ThesisPartModel]:
        """Return the parts with these ids, in no particular order."""
        result = await self._session.execute(
            select(ThesisPartModel).where(ThesisPartModel.id.in_(part_ids))
        )
        return list(result.scalars().all())

    async def find_by_name(
        self, student_id: uuid.UUID, name: str
    ) -> ThesisPartModel | None:
        """Return the part with this name, whatever its case."""
        result = await self._session.execute(
            select(ThesisPartModel).where(
                ThesisPartModel.student_id == student_id,
                func.lower(ThesisPartModel.name) == name.lower(),
            )
        )
        return result.scalar_one_or_none()

    async def next_position(self, student_id: uuid.UUID) -> int:
        """Return the position that puts a new part last."""
        result = await self._session.execute(
            select(func.max(ThesisPartModel.position)).where(
                ThesisPartModel.student_id == student_id
            )
        )
        current: int | None = result.scalar_one_or_none()
        return (current or 0) + 1


class ThesisFragmentRepository:
    """Async store for the fragments handed in for a thesis."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, model: ThesisFragmentModel) -> None:
        """Persist a fragment and commit."""
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)

    async def update(self, model: ThesisFragmentModel) -> None:
        """Commit in-place changes to an already-persisted fragment."""
        await self._session.commit()
        await self._session.refresh(model)

    async def delete(self, model: ThesisFragmentModel) -> None:
        """Delete one fragment and commit."""
        await self._session.delete(model)
        await self._session.commit()

    async def find_by_id(self, fragment_id: uuid.UUID) -> ThesisFragmentModel | None:
        """Return one fragment, or None."""
        return await self._session.get(ThesisFragmentModel, fragment_id)

    async def find_by_student(self, student_id: uuid.UUID) -> list[ThesisFragmentModel]:
        """Return a student's fragments, the latest handed in first."""
        result = await self._session.execute(
            select(ThesisFragmentModel)
            .where(ThesisFragmentModel.student_id == student_id)
            .order_by(
                ThesisFragmentModel.received_on.desc(),
                ThesisFragmentModel.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def find_awaiting_feedback(
        self, student_ids: Sequence[uuid.UUID]
    ) -> list[ThesisFragmentModel]:
        """Return fragments nobody has answered yet, the longest waiting first."""
        result = await self._session.execute(
            select(ThesisFragmentModel)
            .where(
                ThesisFragmentModel.student_id.in_(student_ids),
                ThesisFragmentModel.verdict.is_(None),
            )
            .order_by(ThesisFragmentModel.received_on)
        )
        return list(result.scalars().all())

    async def count_by_part(self, part_id: uuid.UUID) -> int:
        """Return how many rounds a part has."""
        result = await self._session.execute(
            select(func.count())
            .select_from(ThesisFragmentModel)
            .where(ThesisFragmentModel.part_id == part_id)
        )
        return result.scalar_one()

    async def next_round_number(self, part_id: uuid.UUID) -> int:
        """Return the round the next fragment of this part is."""
        result = await self._session.execute(
            select(func.max(ThesisFragmentModel.round_number)).where(
                ThesisFragmentModel.part_id == part_id
            )
        )
        current: int | None = result.scalar_one_or_none()
        return (current or 0) + 1


class ModelSettingRepository:
    """Async store for the admin's local-model allowlist."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def policy(self) -> ModelPolicy:
        """Every setting, as the domain policy (no server default attached)."""
        rows = (await self._session.execute(select(ModelSettingModel))).scalars()
        return ModelPolicy(
            settings=[
                ModelSetting(name=r.name, enabled=r.enabled, is_default=r.is_default)
                for r in rows
            ]
        )

    async def set_enabled(self, name: str, enabled: bool, by: uuid.UUID) -> None:
        row = await self._session.get(ModelSettingModel, name)
        if row is None:
            row = ModelSettingModel(name=name, is_default=False, updated_by=by)
            self._session.add(row)
        row.enabled = enabled
        row.updated_by = by
        row.updated_at = datetime.now(UTC)
        await self._session.commit()

    async def set_default(self, name: str, by: uuid.UUID) -> None:
        """Make `name` the one default, enabling it on the way."""
        now = datetime.now(UTC)
        # Clear the old default first and flush, so the partial unique index
        # never sees two defaults inside the transaction.
        await self._session.execute(
            update(ModelSettingModel)
            .where(ModelSettingModel.is_default.is_(True))
            .values(is_default=False, updated_by=by, updated_at=now)
        )
        await self._session.flush()
        row = await self._session.get(ModelSettingModel, name)
        if row is None:
            row = ModelSettingModel(name=name, updated_by=by)
            self._session.add(row)
        row.enabled = True
        row.is_default = True
        row.updated_by = by
        row.updated_at = now
        await self._session.commit()
