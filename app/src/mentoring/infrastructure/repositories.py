"""Async repositories for persisting mentoring data."""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.mentoring.infrastructure.orm import (
    AgentActionModel,
    MeetingNoteModel,
    StudentModel,
    ThesisDraftModel,
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
    ) -> list[StudentModel]:
        """Return students with optional filters, newest first.

        ``promotor_id=None`` means "every promoter's students" — only callers
        holding VIEW_ALL_STUDENTS ever pass that.
        """
        stmt = select(StudentModel).order_by(StudentModel.created_at.desc())
        if promotor_id is not None:
            stmt = stmt.where(StudentModel.promotor_id == promotor_id)
        if status is not None:
            stmt = stmt.where(StudentModel.status == status)
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
        """Delete the student with the given id if it exists."""
        student = await self._session.get(StudentModel, student_id)
        if student is not None:
            await self._session.delete(student)
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
        promotor_id: uuid.UUID | None,
        limit: int = 30,
    ) -> list[AgentActionModel]:
        """Return the most recently updated actions across a promoter's students.

        ``promotor_id=None`` means every promoter's actions — only a caller
        with ``VIEW_ALL_STUDENTS`` ever passes that, mirroring
        ``StudentRepository.find_all``.
        """
        stmt = select(AgentActionModel).order_by(AgentActionModel.updated_at.desc())
        if promotor_id is not None:
            stmt = stmt.where(AgentActionModel.promotor_id == promotor_id)
        stmt = stmt.limit(limit)
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
