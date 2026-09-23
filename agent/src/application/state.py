"""LangGraph state schema, shared by every action the agent can run."""

import operator
from typing import Annotated, Any

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
    # Summed, not overwritten: the review's three analysis nodes run in
    # parallel, and LangGraph merges what each branch returns with the
    # reducer named here. A plain list would make two branches writing it in
    # the same step an error.
    findings: Annotated[list[Finding], operator.add]
    # Why an analysis branch produced nothing. Collected, never cleared: a
    # later node succeeding must not erase that an earlier one failed.
    node_errors: Annotated[list[str], operator.add]
    scores: list[Score]
    output: dict[str, Any] | None
    status: str
    # The failure of the node that produces the action's result — a
    # single-node action, or the review itself. Analysis branches report
    # through ``node_errors`` instead.
    error: str | None
    model: str
    language: str


class AnalysisUpdate(TypedDict, total=False):
    """What an analysis node hands back: its own findings, or why it failed.

    Only the keys it owns — returning the whole state from a parallel branch
    would write every key from three places at once.
    """

    findings: list[Finding]
    node_errors: list[str]


class ReviewUpdate(TypedDict, total=False):
    """What the review node hands back after the analysis branches join."""

    scores: list[Score]
    output: dict[str, Any] | None
    status: str
    error: str | None
