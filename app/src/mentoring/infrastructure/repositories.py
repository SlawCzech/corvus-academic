"""Async repositories for persisting mentoring data."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.mentoring.infrastructure.models import (
    AgentActionModel,
    MeetingNoteModel,
    StudentModel,
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
