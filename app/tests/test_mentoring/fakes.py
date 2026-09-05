"""Test doubles for the mentoring tests."""

from typing import Any
from uuid import UUID

import httpx

from src.mentoring.application.agent_client import (
    AgentActionStatus,
    AgentClient,
    AgentUnavailableError,
)


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
        self.unavailable = False
        self.next_status = AgentActionStatus("pending", None, None)

    async def submit_action(
        self,
        action_id: UUID,
        action_type: str,
        student_id: UUID,
        context: dict[str, Any],
        token: str,
        model: str | None = None,
        language: str = "pl",
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
            }
        )
        return self.task_id

    async def get_action(self, task_id: str, token: str) -> AgentActionStatus:
        if self.unavailable:
            raise AgentUnavailableError("connection refused")
        self.polls.append(task_id)
        return self.next_status

    def completes_with(self, payload: dict[str, Any]) -> None:
        """Arrange the next poll to report a finished action."""
        self.next_status = AgentActionStatus("completed", payload, None)

    def fails_with(self, message: str) -> None:
        """Arrange the next poll to report a failed action."""
        self.next_status = AgentActionStatus("failed", None, message)


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
