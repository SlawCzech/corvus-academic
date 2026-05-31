"""Celery tasks for the thesis analysis pipeline."""

import dataclasses
from typing import Any, cast
from uuid import UUID

import structlog
from celery import Task, shared_task

from src.application.graph import build_analysis_graph
from src.application.state import AnalysisState, ThesisMetadataDict

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _to_json(obj: Any) -> Any:
    """Recursively convert domain objects to JSON-serializable primitives."""
    if isinstance(obj, UUID):
        return str(obj)
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_json(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [_to_json(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _to_json(v) for k, v in obj.items()}
    return obj


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def analyze_thesis(
    self: Task,  # type: ignore[type-arg]
    evaluation_id: str,
    text: str,
    guidelines: str,
    metadata: dict[str, Any],
    model: str = "qwen3:30b-a3b",
    mode: str = "full",
) -> dict[str, Any]:
    """Run the thesis analysis pipeline as a Celery task.

    mode="full"        — all four analysis nodes
    mode="review_only" — skip to review generation immediately
    model              — ollama model tag to use (overrides settings default)
    """
    logger.info(
        "analyze_thesis.started",
        evaluation_id=evaluation_id,
        model=model,
        mode=mode,
    )
    try:
        state: AnalysisState = cast(
            AnalysisState,
            {
                "evaluation_id": evaluation_id,
                "metadata": cast(ThesisMetadataDict, metadata),
                "text": text,
                "guidelines": guidelines,
                "findings": [],
                "scores": [],
                "review": None,
                "status": "analyzing",
                "error": None,
                "model": model,
                "mode": mode,
            },
        )
        graph = build_analysis_graph(mode=mode)
        result: dict[str, Any] = dict(graph.invoke(state))  # type: ignore[arg-type]
        json_result: dict[str, Any] = _to_json(result)

        # Promote review fields to top level so the frontend AnalysisResult
        # type can read summary and recommendation directly.
        review_data = json_result.get("review")
        if isinstance(review_data, dict):
            json_result["summary"] = review_data.get("summary")
            json_result["recommendation"] = review_data.get("recommendation")

        logger.info("analyze_thesis.completed", evaluation_id=evaluation_id)
        return json_result
    except Exception as exc:
        logger.error(
            "analyze_thesis.failed", evaluation_id=evaluation_id, error=str(exc)
        )
        raise self.retry(exc=exc)  # noqa: B904
