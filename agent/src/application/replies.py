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
    create_model,
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


def _quote_is_required(schema: dict[str, Any]) -> None:
    # Present in every reply Ollama decodes, even as "" — an optional key is
    # one a constrained model is free to never write.
    schema.setdefault("required", []).append("quote")


class FindingReply(_Reply):
    """One defect, as structure, methodology and requirements report it."""

    model_config = ConfigDict(json_schema_extra=_quote_is_required)

    section: Text
    description: Text
    severity: Severity
    suggestion: str
    # Verbatim evidence from the thesis, or "" when the defect is an absence.
    # Defaults to "" so a hosted model that leaves it out is not failed for it.
    quote: str = ""


FINDINGS = TypeAdapter(list[FindingReply])


# ---------- the coherence check: chapter digests ----------


class ClaimReply(_Reply):
    claim: Text
    # Verbatim, like a finding's: the coherence check quotes these back.
    quote: str = ""


class DigestReply(_Reply):
    """What one chapter says, recorded — not judged."""

    summary: Text
    claims: list[ClaimReply] = Field(default_factory=list[ClaimReply])


DIGEST = TypeAdapter(DigestReply)


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

# The three recommendations, per review language, strictest last.
RECOMMENDATIONS: dict[str, tuple[str, str, str]] = {
    "pl": (
        "Dopuścić do obrony",
        "Dopuścić do obrony z zastrzeżeniami",
        "Zwrócić do poprawy",
    ),
    "en": (
        "Approved for defense",
        "Approved for defense with reservations",
        "Returned for revision",
    ),
}


def review_reply_for(allowed: tuple[str, ...]) -> TypeAdapter[ReviewReply]:
    """The review's shape with the recommendation narrowed to ``allowed``.

    Which recommendations are possible follows from the findings — a
    CRITICAL one means "return", none means one of the other two — and a
    model left to apply that rule from the prompt broke it (the evals caught
    a sound thesis returned for revision). As a Literal in the schema,
    Ollama cannot decode anything else, and any other backend gets the
    allowed values back in the repair turn.
    """
    # Built at runtime, so no static type can describe it.
    recommendation: Any = (
        Literal[allowed],  # pyright: ignore[reportInvalidTypeForm]
        Field(validation_alias=AliasChoices("recommendation", "decision")),
    )
    narrowed = create_model(
        "ConstrainedReviewReply",
        __base__=ReviewReply,
        recommendation=recommendation,
    )
    return TypeAdapter(narrowed)


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


class FragmentChangeReply(_Reply):
    point: Text
    quote: str = ""


class FragmentReviewReply(_Reply):
    summary: Text
    answer: str = ""
    direction: Annotated[
        Literal["on_track", "needs_changes", "needs_additions"],
        BeforeValidator(_lower),
    ]
    strengths: list[str] = Field(default_factory=list[str])
    changes: list[FragmentChangeReply] = Field(
        default_factory=list[FragmentChangeReply]
    )
    additions: list[str] = Field(default_factory=list[str])
    addressed: list[str] = Field(default_factory=list[str])
    next_step: str = ""


FRAGMENT_REVIEW = TypeAdapter(FragmentReviewReply)


class MeetingNoteReply(_Reply):
    content: Text
    topics_discussed: list[str] = Field(default_factory=list[str])
    agreed_actions: list[str] = Field(default_factory=list[str])


MEETING_NOTE = TypeAdapter(MeetingNoteReply)


# ---------- the bibliography check ----------


class ReferenceReply(_Reply):
    """One entry of the bibliography, as written and taken apart."""

    entry: Text
    authors: str = ""
    year: int | None = None
    title: str = ""
    venue: str = ""


class ReferencesReply(_Reply):
    references: list[ReferenceReply] = Field(default_factory=list[ReferenceReply])


REFERENCES = TypeAdapter(ReferencesReply)


class VerdictReply(_Reply):
    """The agent's conclusion about one reference it investigated."""

    index: int
    status: Annotated[
        Literal["found", "mismatch", "not_indexed", "suspicious"],
        BeforeValidator(_lower),
    ]
    note: str = ""
    doi: str = ""


class VerdictsReply(_Reply):
    verdicts: list[VerdictReply] = Field(default_factory=list[VerdictReply])


VERDICTS = TypeAdapter(VerdictsReply)
