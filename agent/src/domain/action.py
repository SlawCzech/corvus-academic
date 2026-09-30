"""Vocabulary shared by every AI action the agent can run.

Deliberately duplicated in `app`'s mentoring context rather than imported:
the two services share a wire contract, not a codebase — the same reason
`api/auth.py` keeps its own copy of `Role`.
"""

from enum import StrEnum

# Providers a user may bring their own key for. Self-hosted Ollama needs no
# key and is what runs when nobody brought one.
SUPPORTED_PROVIDERS: frozenset[str] = frozenset({"claude", "openai"})


class ActionType(StrEnum):
    """Kind of AI action requested by `app`."""

    PROPOSE_TOPIC = "propose_topic"
    EVALUATE_METHODOLOGY = "evaluate_methodology"
    CHECK_PROGRESS = "check_progress"
    DRAFT_MEETING_NOTE = "draft_meeting_note"
    DEFENCE_QUESTIONS = "defence_questions"
    GENERATE_REVIEW = "generate_review"
    VERIFY_BIBLIOGRAPHY = "verify_bibliography"


class TaskStatus(StrEnum):
    """Lifecycle of one dispatched task, as persisted in Postgres.

    Persisted by the worker itself — not derived from Celery's Redis result
    backend, whose entries expire (~1 day) and would take the history of a
    student's actions with them.
    """

    PENDING = "pending"
    RUNNING = "running"
    # Paused inside the graph for the promoter's decision (an `interrupt`):
    # nothing runs, the checkpoint holds the state, and a resume continues it.
    AWAITING_INPUT = "awaiting_input"
    COMPLETED = "completed"
    FAILED = "failed"
    # Stopped by the promoter. Final: a worker finishing late does not
    # overwrite it (see AgentTaskRepository.update_status).
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        """Return True when no further status change is expected."""
        return self in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
