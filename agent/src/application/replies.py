"""The shape of every model reply a node accepts.

One Pydantic model per reply. `structured.invoke_structured` turns each into
a JSON schema for Ollama's constrained decoding and validates every backend's
reply against it, so a node receives typed data or a precise error — never a
dict it has to probe with ``.get(...) or []``.

Tolerance lives here, not in the nodes: enum-like fields are lower-cased
before they are checked ("Major" is a hosted model's habit, not a defect), and
the review's fields accept the synonyms models reach for. What the frontend
reads is the ``model_dump()`` of these — the same keys the prompts ask for.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    TypeAdapter,
)


def _lower(value: Any) -> Any:  # noqa: ANN401
    return value.strip().lower() if isinstance(value, str) else value


# Required text: whitespace alone is as empty as nothing.
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

Severity = Annotated[Literal["critical", "major", "minor"], BeforeValidator(_lower)]


class _Reply(BaseModel):
    # Extra keys are dropped, not rejected: a model adding "confidence" to a
    # finding has not got the finding wrong.
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


# ---------- the review's analysis nodes ----------


class FindingReply(_Reply):
    """One defect, as structure, methodology and requirements report it."""

    section: Text
    description: Text
    severity: Severity
    suggestion: str


FINDINGS = TypeAdapter(list[FindingReply])


# ---------- the review ----------


class ScoreReply(_Reply):
    criteria: Text = Field(
        validation_alias=AliasChoices("criteria", "criterion", "name", "category"),
    )
    points: int = Field(ge=0, le=10, validation_alias=AliasChoices("points", "score"))
    max_points: int = Field(
        default=10, validation_alias=AliasChoices("max_points", "max", "maximum")
    )


class ReviewReply(_Reply):
    scores: list[ScoreReply] = Field(min_length=1)
    review_text: Text = Field(
        validation_alias=AliasChoices("review_text", "summary", "review")
    )
    recommendation: Text = Field(
        validation_alias=AliasChoices("recommendation", "decision")
    )


REVIEW = TypeAdapter(ReviewReply)


# ---------- single-node actions ----------


class TopicReply(_Reply):
    title: Text
    rationale: str = ""
    scope: str = ""
    risks: str = ""


class TopicProposalReply(_Reply):
    topics: list[TopicReply] = Field(min_length=1)
    recommended: int = 0


TOPIC_PROPOSAL = TypeAdapter(TopicProposalReply)


class QuestionReply(_Reply):
    question: Text
    rationale: str = ""
    section: str = ""
    focus: Annotated[
        Literal["problem", "method", "conclusions"], BeforeValidator(_lower)
    ]


class DefenceQuestionsReply(_Reply):
    questions: list[QuestionReply] = Field(min_length=1)


DEFENCE_QUESTIONS = TypeAdapter(DefenceQuestionsReply)


class ChangeReply(_Reply):
    area: str = ""
    change: Text
    assessment: Annotated[
        Literal["progress", "cosmetic", "regression"], BeforeValidator(_lower)
    ]


class ProgressReply(_Reply):
    summary: Text
    changes: list[ChangeReply] = Field(default_factory=list[ChangeReply])
    concerns: list[str] = Field(default_factory=list[str])
    next_steps: list[str] = Field(default_factory=list[str])


PROGRESS = TypeAdapter(ProgressReply)


class MeetingNoteReply(_Reply):
    content: Text
    topics_discussed: list[str] = Field(default_factory=list[str])
    agreed_actions: list[str] = Field(default_factory=list[str])


MEETING_NOTE = TypeAdapter(MeetingNoteReply)
