"""LangGraph node: generate final review and scores."""

import json
from collections.abc import Sequence
from uuid import UUID

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from src.application.prompts import review as prompts
from src.domain.analysis import ThesisAnalysis
from src.domain.evaluation import EvaluationStatus, ThesisEvaluation
from src.domain.metadata import ThesisMetadata
from src.domain.review import Review, Score
from src.infrastructure.llm_factory import get_llm

from ..state import AnalysisState

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def generate_review(state: AnalysisState) -> AnalysisState:
    """Generate final review with scores and update evaluation status."""
    try:
        llm = get_llm()
        findings_summary = "\n".join(
            f"[{f.severity}] {f.section}: {f.description}"
            for f in state["findings"]
        )
        messages = [
            SystemMessage(content=prompts.SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Thesis text:\n{state['text']}\n\n"
                    f"Guidelines:\n{state['guidelines']}\n\n"
                    f"Accumulated findings:\n{findings_summary or 'None'}"
                )
            ),
        ]
        response = llm.invoke(messages)
        raw: str | Sequence[object] = response.content  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        content: str = raw if isinstance(raw, str) else json.dumps(raw)
        data: dict[str, object] = json.loads(content)

        scores_data: list[dict[str, object]] = data["scores"]  # type: ignore[assignment]
        scores: list[Score] = [
            Score(
                criteria=str(s["criteria"]),
                points=int(str(s["points"])),
                max_points=int(str(s["max_points"])),
            )
            for s in scores_data
        ]

        evaluation_uuid = UUID(state["evaluation_id"])
        review = Review(
            review_id=evaluation_uuid,
            thesis_id=evaluation_uuid,
            scores=scores,
            summary=str(data["summary"]),
            recommendation=str(data["recommendation"]),
        )

        # Use the domain aggregate to determine ANALYZED vs REJECTED status.
        meta = state["metadata"]
        thesis_metadata = ThesisMetadata(
            author=meta["author"],
            title=meta["title"],
            year=meta["year"],
            field_of_study=meta["field_of_study"],
        )
        analysis = ThesisAnalysis(
            thesis_id=evaluation_uuid,
            findings=state["findings"],
        )
        evaluation = ThesisEvaluation(
            id=evaluation_uuid,
            metadata=thesis_metadata,
            status=EvaluationStatus.ANALYZING,
        )
        evaluation.complete_analysis(analysis)

        logger.info(
            "review_generated",
            recommendation=review.recommendation,
            status=evaluation.status.value,
            score=review.total_percentage(),
        )

        result: AnalysisState = state.copy()
        result["scores"] = scores
        result["review"] = review
        result["status"] = evaluation.status.value
        result["error"] = None
        return result
    except Exception as exc:
        logger.error("review_generation_failed", error=str(exc))
        result = state.copy()
        result["error"] = str(exc)
        return result
