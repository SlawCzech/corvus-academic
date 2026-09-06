"""Celery task: run one AI action for one student."""

import dataclasses
from typing import Any, cast
from uuid import UUID

import structlog
from celery import Task, shared_task

from src.application.graph import build_action_graph
from src.application.guidelines import load_guidelines
from src.application.state import ActionState
from src.domain.action import ActionType, TaskStatus
from src.domain.analysis import ThesisType
from src.infrastructure.llm_factory import ModelCredentials, use_credentials
from src.infrastructure.task_status import record_task_status

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Keys of the final graph state worth keeping. `context` is deliberately
# dropped: it holds the inputs, it can reach 2 MB of thesis text, and
# everything downstream (HTTP response, frontend, persisted row) reads output.
_RESULT_KEYS = (
    "action_id",
    "action_type",
    "findings",
    "scores",
    "output",
    "status",
    "error",
)


# Actions judged against university requirements. The guideline text is
# `agent`-owned static data (files today, pgvector in Phase 5), so it is loaded
# here rather than shipped over the wire by `app`.
_ACTIONS_NEEDING_GUIDELINES = frozenset(
    {ActionType.GENERATE_REVIEW, ActionType.EVALUATE_METHODOLOGY}
)


def _with_guidelines(action_type: str, context: dict[str, Any]) -> dict[str, Any]:
    """Add the university requirements to the context, if the action needs them."""
    if action_type not in _ACTIONS_NEEDING_GUIDELINES or "guidelines" in context:
        return context
    thesis_type = str(context.get("thesis_type", ThesisType.BACHELOR))
    return {**context, "guidelines": load_guidelines(thesis_type)}


def _to_json(obj: Any) -> Any:  # noqa: ANN401
    """Recursively convert domain objects to JSON-serializable primitives."""
    if isinstance(obj, UUID):
        return str(obj)
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_json(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [_to_json(item) for item in cast(list[Any], obj)]
    if isinstance(obj, dict):
        return {
            key: _to_json(value)
            for key, value in cast(dict[str, Any], obj).items()
        }
    return obj


def _result_payload(state: dict[str, Any]) -> dict[str, Any]:
    """Reduce a finished graph state to the payload stored and returned.

    Output fields are promoted to the top level so the frontend's
    AnalysisResult type keeps reading summary and recommendation directly.
    """
    json_state: dict[str, Any] = _to_json(state)
    payload: dict[str, Any] = {
        key: json_state.get(key) for key in _RESULT_KEYS if key in json_state
    }
    output = json_state.get("output")
    if isinstance(output, dict):
        for key in ("summary", "recommendation"):
            if key in output:
                payload[key] = output[key]
    return payload


def _initial_state(
    action_id: str,
    action_type: str,
    student_id: str,
    context: dict[str, Any],
    model: str,
    language: str,
) -> ActionState:
    return cast(
        ActionState,
        {
            "action_id": action_id,
            "action_type": action_type,
            "student_id": student_id,
            "context": context,
            "findings": [],
            "scores": [],
            "output": None,
            "status": "running",
            "error": None,
            "model": model,
            "language": language,
        },
    )


def _run_graph(
    task_id: str | None, state: ActionState, mode: str = "full"
) -> dict[str, Any]:
    """Run the graph for this action, recording status on both sides of it."""
    record_task_status(task_id, TaskStatus.RUNNING)
    graph = build_action_graph(state["action_type"], mode=mode)
    result: dict[str, Any] = dict(graph.invoke(state))  # type: ignore[arg-type]
    payload = _result_payload(result)

    # Nodes never raise — they record the problem in state and let the graph
    # finish. An error surviving to the end means the last node produced
    # nothing usable, so the task is a failure the promoter should see, not a
    # success with an empty result.
    node_error = result.get("error")
    if node_error:
        record_task_status(
            task_id, TaskStatus.FAILED, result=payload, error=str(node_error)
        )
    else:
        record_task_status(task_id, TaskStatus.COMPLETED, result=payload)
    return payload


def _record_final_failure(task: Task, task_id: str | None, exc: Exception) -> None:  # type: ignore[type-arg]
    """Persist a failure only when no retry is coming."""
    max_retries: int | None = task.max_retries
    if max_retries is not None and task.request.retries >= max_retries:
        record_task_status(task_id, TaskStatus.FAILED, error=str(exc))


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def run_action(
    self: Task,  # type: ignore[type-arg]
    action_id: str,
    action_type: str,
    student_id: str,
    context: dict[str, Any],
    model: str = "qwen3:30b-a3b",
    language: str = "pl",
    provider: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Run one AI action for one student.

    `context` arrives fully assembled from `app` — the agent never calls back
    for data mid-task, so a worker's job never depends on `app` being up.

    The user's own provider key, when they brought one, arrives as its own
    argument and is held only for the duration of the graph run. It is never
    put into the state, which is what gets serialised into the stored result.
    """
    task_id: str | None = self.request.id
    credentials = (
        ModelCredentials(provider=provider, api_key=api_key)
        if provider and api_key
        else None
    )
    logger.info(
        "run_action.started",
        action_id=action_id,
        action_type=action_type,
        student_id=student_id,
        task_id=task_id,
        model=model,
        # The provider is worth knowing; the key is never logged.
        byok_provider=credentials.provider if credentials else None,
    )
    try:
        with use_credentials(credentials):
            payload = _run_graph(
                task_id,
                _initial_state(
                    action_id,
                    action_type,
                    student_id,
                    _with_guidelines(action_type, context),
                    model,
                    language,
                ),
            )
        logger.info("run_action.completed", action_id=action_id)
        return payload
    except Exception as exc:
        logger.error("run_action.failed", action_id=action_id, error=str(exc))
        _record_final_failure(self, task_id, exc)
        raise self.retry(exc=exc)  # noqa: B904
