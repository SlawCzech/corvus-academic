"""Use cases for one-off reviews: a thesis with nobody to supervise (ADR 0017).

A one-off review is a hidden student, so this is only what differs: making
one, listing them, and turning one into a student. Everything else — actions,
retention, delete — runs through the ordinary paths.
"""

from dataclasses import dataclass
from uuid import UUID

import structlog

from src.document.extractor import extract
from src.document.title_page import TitlePage, read_title_page
from src.mentoring.application.draft_service import DraftService, DraftView
from src.mentoring.application.student_service import Caller, StudentService
from src.mentoring.domain.student import Student, ThesisType

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ReviewView:
    """A one-off review as the promoter sees it: the row and its one thesis."""

    student: Student
    draft: DraftView


class ReviewService:
    """Makes one-off reviews, lists them, and promotes them to students."""

    def __init__(self, students: StudentService, drafts: DraftService) -> None:
        self._students = students
        self._drafts = drafts

    def suggest(
        self, filename: str, data: bytes, content_type: str = ""
    ) -> TitlePage:
        """Read a thesis's title page for the form. Nothing is stored.

        Raises ValueError for an unsupported or unreadable file.
        """
        return read_title_page(extract(data, filename, content_type).text)

    async def create(
        self,
        caller: Caller,
        full_name: str,
        field_of_study: str,
        thesis_type: ThesisType,
        filename: str,
        data: bytes,
        content_type: str = "",
        topic: str | None = None,
        research_area: str | None = None,
        research_aim: str | None = None,
    ) -> ReviewView:
        """Store a one-off review and its thesis, both or neither.

        The thesis upload commits the row too, so a file nobody can read
        leaves nothing in the history. No action starts here: it goes through
        the ordinary trigger, and a missing key there costs no half-made
        review.

        Raises ValueError for blank fields or an unusable file.
        """
        student = await self._students.add_one_off(
            caller,
            full_name=full_name,
            field_of_study=field_of_study,
            thesis_type=thesis_type,
            topic=topic,
            research_area=research_area,
            research_aim=research_aim,
        )
        try:
            draft = await self._drafts.upload(
                caller,
                student.id,
                filename=filename,
                data=data,
                content_type=content_type,
            )
        except Exception:
            await self._students.discard_unsaved()
            raise
        logger.info(
            "one_off_review_created",
            student_id=str(student.id),
            promotor_id=str(caller.user_id),
        )
        return ReviewView(student, draft)

    async def list_reviews(self, caller: Caller) -> list[ReviewView]:
        """Return the caller's one-off reviews, newest first."""
        students = await self._students.list_students(caller, one_off=True)
        return [
            ReviewView(s, (await self._drafts.list_drafts(caller, s.id))[0])
            for s in students
        ]

    async def promote(self, caller: Caller, review_id: UUID) -> Student:
        """Put the review's author on the roster; there is no way back.

        Raises StudentNotFoundError when the caller may not see the row, and
        ValueError when it is already a student.
        """
        student = await self._students.promote(caller, review_id)
        logger.info("one_off_review_promoted", student_id=str(student.id))
        return student
