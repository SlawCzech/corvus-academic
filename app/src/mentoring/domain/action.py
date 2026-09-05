"""Domain entities for AI actions run against a student.

One entity for every action type, not one per type: they share the same
lifecycle (trigger → dispatch → poll → structured output → accept), and what
differs between them is the shape of ``output``, which is JSON.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, cast
from uuid import UUID


class ActionType(StrEnum):
    """AI action that can be run against a student."""

    PROPOSE_TOPIC = "propose_topic"
    EVALUATE_METHODOLOGY = "evaluate_methodology"
    CHECK_PROGRESS = "check_progress"
    DRAFT_MEETING_NOTE = "draft_meeting_note"
    GENERATE_REVIEW = "generate_review"


class ActionStatus(StrEnum):
    """Lifecycle of one action, mirroring what `agent` persists.

    The same four values on both sides of the wire: the agent writes them to
    its own row, `app` copies them here, and neither depends on Celery's
    expiring result backend to know what happened.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        """Return True when no further status change is expected."""
        return self in (ActionStatus.COMPLETED, ActionStatus.FAILED)


@dataclass
class AgentAction:
    """One AI action: what was asked, what came back, whether it was accepted."""

    id: UUID
    student_id: UUID
    promotor_id: UUID
    action_type: ActionType
    status: ActionStatus = ActionStatus.PENDING
    task_id: str | None = None
    detail: str | None = None
    output: dict[str, Any] | None = None
    error: str | None = None
    accepted: bool = False
    accepted_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_finished(self) -> bool:
        """Return True once the agent has stopped working on this action."""
        return self.status.is_terminal

    @property
    def can_be_accepted(self) -> bool:
        """Only a completed action that nobody accepted yet can be accepted."""
        return self.status is ActionStatus.COMPLETED and not self.accepted

    def proposed_topics(self) -> list[dict[str, Any]]:
        """Return the topics a `propose_topic` action came back with.

        The agent's payload wraps each action's own structured result under
        ``output``; everything else in it (findings, scores) belongs to the
        review actions.
        """
        payload = self.output or {}
        structured = payload.get("output")
        if not isinstance(structured, dict):
            return []
        topics = cast(dict[str, Any], structured).get("topics")
        if not isinstance(topics, list):
            return []
        return [t for t in cast(list[Any], topics) if isinstance(t, dict)]

    def topic_title(self, index: int) -> str:
        """Return the title of one proposed topic.

        Raises ValueError for an index nobody proposed — the promoter picks
        from what the model actually returned.
        """
        topics = self.proposed_topics()
        if not 0 <= index < len(topics):
            raise ValueError(
                f"No proposed topic at index {index} (got {len(topics)})"
            )
        title = str(topics[index].get("title", "")).strip()
        if not title:
            raise ValueError(f"Proposed topic {index} has no title")
        return title

    def accept(self, at: datetime | None = None) -> None:
        """Mark the action accepted by the promoter."""
        if not self.can_be_accepted:
            raise ValueError(f"Action in status {self.status} cannot be accepted")
        self.accepted = True
        self.accepted_at = at or datetime.now(UTC)
