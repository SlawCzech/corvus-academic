"""Test doubles for the mentoring tests."""

import io
from typing import Any
from uuid import UUID

import httpx
from docx import Document as DocxDocument

from src.mentoring.application.agent_client import (
    BYOK,
    AgentActionStatus,
    AgentClient,
)
from src.mentoring.application.exceptions import AgentUnavailableError
from src.mentoring.application.guidelines_port import GuidelineRubric


class FakeAgentClient(AgentClient):
    """An agent that records what it was asked and answers what it is told to.

    Subclasses the real client so the service is exercised through the type
    it actually depends on; no request ever leaves the process.
    """

    def __init__(self, task_id: str = "task-1") -> None:
        super().__init__(httpx.AsyncClient(), "http://agent:8002")
        self.task_id = task_id
        self.submitted: list[dict[str, Any]] = []
        self.polls: list[str] = []
        self.cancelled: list[str] = []
        self.resumed: list[dict[str, Any]] = []
        self.deleted: list[str] = []
        self.deleted_students: list[UUID] = []
        self.unavailable = False
        self.next_status = AgentActionStatus("pending", None, None)
        self.models: dict[str, Any] = {
            "backend": "ollama",
            "default": "qwen3:30b-a3b",
            "local": [
                {"name": "gemma4:12b", "parameter_size": "11.9B"},
                {"name": "qwen3:30b-a3b", "parameter_size": "30.5B"},
                {"name": "llama3.1:latest", "parameter_size": "8.0B"},
            ],
            "local_available": True,
            "byok": {"claude": "claude-sonnet-4-20250514", "openai": "gpt-4o"},
        }

    async def submit_action(
        self,
        action_id: UUID,
        action_type: str,
        student_id: UUID,
        context: dict[str, Any],
        token: str,
        model: str | None = None,
        language: str = "pl",
        byok: BYOK | None = None,
    ) -> str:
        if self.unavailable:
            raise AgentUnavailableError("connection refused")
        self.submitted.append(
            {
                "action_id": action_id,
                "action_type": action_type,
                "student_id": student_id,
                "context": context,
                "token": token,
                "model": model,
                "language": language,
                "byok": byok,
            }
        )
        return self.task_id

    async def get_action(self, task_id: str, token: str) -> AgentActionStatus:
        if self.unavailable:
            raise AgentUnavailableError("connection refused")
        self.polls.append(task_id)
        return self.next_status

    async def resume_action(
        self,
        task_id: str,
        decision: dict[str, Any],
        token: str,
        byok: BYOK | None = None,
    ) -> None:
        if self.unavailable:
            raise AgentUnavailableError("connection refused")
        self.resumed.append({"task_id": task_id, "decision": decision, "byok": byok})

    def pauses_with(self, payload: dict[str, Any]) -> None:
        """Arrange the next poll to report a review paused for the promoter."""
        self.next_status = AgentActionStatus(
            "awaiting_input", payload, None, {"steps": [], "done": []}
        )

    async def cancel_action(self, task_id: str, token: str) -> AgentActionStatus:
        if self.unavailable:
            raise AgentUnavailableError("connection refused")
        self.cancelled.append(task_id)
        return AgentActionStatus("cancelled", None, None)

    async def delete_action(self, task_id: str, token: str) -> None:
        if self.unavailable:
            raise AgentUnavailableError("connection refused")
        self.deleted.append(task_id)

    async def delete_student_actions(self, student_id: UUID, token: str) -> None:
        if self.unavailable:
            raise AgentUnavailableError("connection refused")
        self.deleted_students.append(student_id)

    async def list_models(self, token: str) -> dict[str, Any]:
        if self.unavailable:
            raise AgentUnavailableError("connection refused")
        return self.models

    def completes_with(
        self, payload: dict[str, Any], usage: dict[str, Any] | None = None
    ) -> None:
        """Arrange the next poll to report a finished action."""
        self.next_status = AgentActionStatus("completed", payload, None, usage=usage)

    def runs_with(self, progress: dict[str, Any]) -> None:
        """Arrange the next poll to report a running action and how far it got."""
        self.next_status = AgentActionStatus("running", None, None, progress)

    def fails_with(self, message: str, code: str | None = None) -> None:
        """Arrange the next poll to report a failed action."""
        self.next_status = AgentActionStatus("failed", None, message, error_code=code)


def topic_payload(*titles: str, recommended: int = 0) -> dict[str, Any]:
    """Build an agent payload shaped like a finished propose_topic action."""
    return {
        "action_type": "propose_topic",
        "findings": [],
        "scores": [],
        "output": {
            "topics": [
                {"title": t, "rationale": "bo tak", "scope": "…", "risks": "…"}
                for t in titles
            ],
            "recommended": recommended,
        },
        "status": "proposed",
        "error": None,
    }


def docx_bytes(*paragraphs: str) -> bytes:
    """Build a minimal DOCX in memory, so an upload test uploads a real file."""
    doc = DocxDocument()  # pyright: ignore[reportCallIssue]
    for text in paragraphs or ("Rozdział 1: Wprowadzenie.",):
        doc.add_paragraph(text)  # pyright: ignore[reportUnknownMemberType]
    buf = io.BytesIO()
    doc.save(buf)  # pyright: ignore[reportUnknownMemberType]
    return buf.getvalue()


def question_payload(*questions: str) -> dict[str, Any]:
    """Build an agent payload shaped like a finished defence_questions action."""
    return {
        "action_type": "defence_questions",
        "findings": [],
        "scores": [],
        "output": {
            "questions": [
                {
                    "question": q,
                    "rationale": "sprawdza rozumienie pracy",
                    "section": "Rozdział 2",
                    "focus": "method",
                }
                for q in questions
            ]
        },
        "status": "questions_ready",
        "error": None,
    }


def note_payload(content: str) -> dict[str, Any]:
    """Build an agent payload shaped like a finished draft_meeting_note action."""
    return {
        "action_type": "draft_meeting_note",
        "findings": [],
        "scores": [],
        "output": {
            "content": content,
            "topics_discussed": ["Zakres rozdziału 2"],
            "agreed_actions": ["Projekt badawczy do 15 marca"],
        },
        "status": "drafted",
        "error": None,
    }


class FakeGuidelineSource:
    """A guideline catalog holding whatever sets a test puts in it."""

    def __init__(self) -> None:
        self.sets: dict[UUID, tuple[str, GuidelineRubric | None]] = {}

    def publish(self, set_id: UUID, thesis_type: str, rubric_md: str) -> UUID:
        """Put a set with a published rubric in the catalog; return the version id."""
        version_id = UUID(int=len(self.sets) + 1)
        self.sets[set_id] = (thesis_type, GuidelineRubric(version_id, rubric_md))
        return version_id

    async def thesis_type_of(self, set_id: UUID) -> str | None:
        entry = self.sets.get(set_id)
        return entry[0] if entry and entry[1] else None

    async def current_rubric(self, set_id: UUID) -> GuidelineRubric | None:
        entry = self.sets.get(set_id)
        return entry[1] if entry else None

    async def first_set_for(self, thesis_type: str) -> UUID | None:
        return next(
            (
                set_id
                for set_id, (kind, rubric) in self.sets.items()
                if kind == thesis_type and rubric
            ),
            None,
        )
