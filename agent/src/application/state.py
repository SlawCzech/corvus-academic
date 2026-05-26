"""LangGraph state schema for the analysis pipeline."""

from typing_extensions import TypedDict

from src.domain.analysis import Finding
from src.domain.review import Review, Score


class ThesisMetadataDict(TypedDict):
    """Serialized form of ThesisMetadata for graph state."""

    author: str
    title: str
    year: int
    field_of_study: str


class AnalysisState(TypedDict):
    """State passed between nodes in the thesis analysis graph."""

    evaluation_id: str
    metadata: ThesisMetadataDict
    text: str
    guidelines: str
    findings: list[Finding]
    scores: list[Score]
    review: Review | None
    status: str
    error: str | None
