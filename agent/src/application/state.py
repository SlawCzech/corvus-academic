"""LangGraph state schema, shared by every action the agent can run."""

from typing import Any

from typing_extensions import TypedDict

from src.domain.analysis import Finding
from src.domain.review import Score


class ThesisMetadataDict(TypedDict):
    """Serialized ThesisMetadata — the shape of ``context["metadata"]``."""

    author: str
    title: str
    year: int
    field_of_study: str
    thesis_type: str
    review_tone: str


class ActionState(TypedDict):
    """State passed between nodes, whatever action is running.

    Everything action-specific lives in ``context``, assembled by `app`
    before dispatch: thesis text, guidelines, metadata, the promoter's
    free-text detail, prior findings. Keeping it in one bag is what lets one
    state schema serve five actions instead of five near-identical schemas —
    and what keeps a new action from being a change to this file.

    ``findings`` and ``scores`` stay first-class because nodes accumulate
    them across a multi-node graph; ``output`` is the action's own structured
    result, ready to be handed back to `app`.
    """

    action_id: str
    action_type: str
    student_id: str
    context: dict[str, Any]
    findings: list[Finding]
    scores: list[Score]
    output: dict[str, Any] | None
    status: str
    error: str | None
    model: str
    language: str
