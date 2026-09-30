"""Builders for graph state used across node, graph and task tests.

One factory rather than a hand-rolled dict per test file: `ActionState` gains
keys as actions are added, and five copies of the same literal would drift.
"""

from typing import Any, cast

from src.application.state import ActionState
from src.domain.action import ActionType
from src.domain.analysis import Finding
from src.domain.review import Score

ACTION_ID = "550e8400-e29b-41d4-a716-446655440000"
STUDENT_ID = "11111111-2222-3333-4444-555555555555"


def make_state(
    action_type: str = ActionType.GENERATE_REVIEW,
    context: dict[str, Any] | None = None,
    findings: list[Finding] | None = None,
    scores: list[Score] | None = None,
    action_id: str = ACTION_ID,
    model: str = "qwen3:30b-a3b",
    language: str = "pl",
    status: str = "running",
) -> ActionState:
    """Build an ActionState with everything a node is entitled to expect."""
    return cast(
        ActionState,
        {
            "action_id": action_id,
            "action_type": action_type,
            "student_id": STUDENT_ID,
            "context": context if context is not None else {},
            "findings": findings if findings is not None else [],
            "node_errors": [],
            "chapter_digests": [],
            "scores": scores if scores is not None else [],
            "verification": None,
            "output": None,
            "status": status,
            "error": None,
            "model": model,
            "language": language,
        },
    )
