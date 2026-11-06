"""Vocabulary shared by every AI action the agent can run.

Deliberately duplicated in `app`'s mentoring context rather than imported:
the two services share a wire contract, not a codebase — the same reason
`api/auth.py` keeps its own copy of `Role`.
"""

from datetime import UTC, datetime, timedelta
from enum import StrEnum

# Providers a user may bring their own key for; every action runs on one.
SUPPORTED_PROVIDERS: frozenset[str] = frozenset({"claude", "openai"})


class ActionType(StrEnum):
    """Kind of AI action requested by `app`."""

    PROPOSE_TOPIC = "propose_topic"
    EVALUATE_METHODOLOGY = "evaluate_methodology"
    CHECK_PROGRESS = "check_progress"
    DRAFT_MEETING_NOTE = "draft_meeting_note"
    DRAFT_STUDENT_EMAIL = "draft_student_email"
    DEFENCE_QUESTIONS = "defence_questions"
    GENERATE_REVIEW = "generate_review"
    TRIAL_REVIEW = "trial_review"
    VERIFY_BIBLIOGRAPHY = "verify_bibliography"
    REVIEW_FRAGMENT = "review_fragment"
    # The one action with no student: an admin's rubric from a regulation.
    DRAFT_RUBRIC = "draft_rubric"


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


class ActionErrorCode(StrEnum):
    """Why a failed task failed, when the promoter can do something about it.

    Travels next to the free-text error, which stays whatever the provider
    said. `app` stores the code and the frontend turns it into advice; a
    failure without a code is one the promoter can only retry.
    """

    # The account behind the key has no money left: top it up, or remove
    # the key and run on the self-hosted model.
    PROVIDER_NO_CREDITS = "provider_no_credits"
    # The provider refused the key itself — revoked, mistyped, no access.
    PROVIDER_KEY_REJECTED = "provider_key_rejected"
    # Too many requests for the account's tier, and the retries ran out.
    PROVIDER_RATE_LIMITED = "provider_rate_limited"


# A pending or running task whose row has not moved for this long is not
# coming back. A run touches its row at every finished node, no node outlives
# the worker's 30-minute time limit, and a dead worker's task is redelivered
# within the 45-minute visibility timeout (`infrastructure/celery_app.py`);
# the rest is room for a redelivered task to wait its turn in the queue.
ABANDONED_AFTER = timedelta(minutes=90)


def is_abandoned(status: str, updated_at: datetime, now: datetime) -> bool:
    """Whether a task that should be moving has stopped for good.

    Only pending and running count: a run paused for the promoter waits for
    them as long as it takes, and a finished one has nothing left to do.
    """
    if status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
        return False
    if updated_at.tzinfo is None:  # SQLite in tests forgets the zone
        updated_at = updated_at.replace(tzinfo=UTC)
    return now - updated_at > ABANDONED_AFTER
