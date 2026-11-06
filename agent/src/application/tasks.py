"""Celery task: run one AI action for one student."""

import dataclasses
from typing import Any, NoReturn, cast
from uuid import UUID

import structlog
from celery import Task, shared_task
from celery.exceptions import SoftTimeLimitExceeded
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from src.application.graph import CompiledActionGraph, build_action_graph
from src.application.nodes.promoter_review import PROMOTER_REVIEWS_FINDINGS
from src.application.state import ActionState
from src.domain.action import TaskStatus
from src.infrastructure.checkpoints import delete as delete_checkpoints
from src.infrastructure.checkpoints import open_checkpointer
from src.infrastructure.deliveries import count_delivery
from src.infrastructure.key_transit import KeyUnsealError, unseal
from src.infrastructure.llm_factory import (
    ModelCredentials,
    model_label,
    use_credentials,
)
from src.infrastructure.provider_errors import classify as classify_provider_error
from src.infrastructure.task_status import (
    read_task_status,
    record_task_progress,
    record_task_status,
    record_task_usage,
)
from src.infrastructure.tracing import flush as flush_traces
from src.infrastructure.tracing import run_config
from src.infrastructure.usage import UsageMeter

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Keys of the final graph state worth keeping. `context` is deliberately
# dropped: it holds the inputs, it can reach 2 MB of thesis text, and
# everything downstream (HTTP response, frontend, persisted row) reads output.
_RESULT_KEYS = (
    "action_id",
    "action_type",
    "findings",
    "node_errors",
    "verification",
    "scores",
    "output",
    "status",
    "error",
)


# How many times one attempt of a task may be delivered before the worker
# stops taking it. One is the normal case; every deploy that lands mid-run
# hands the run back once more (a cold shutdown, see the composes). Past
# this, the run is what keeps killing the worker (`deliveries`).
_MAX_DELIVERIES = 4

# Shown to the promoter as is, like any error without a code.
_KILLS_WORKER = (
    "Przebieg tej akcji kilka razy z rzędu przerwał pracę serwera, więc nie "
    "jest już ponawiany. Zgłoś to administratorowi."
)
_TIMED_OUT = (
    "Akcja trwała dłużej niż 30 minut i została przerwana. Uruchom ją ponownie; "
    "jeśli to się powtórzy, zgłoś to administratorowi."
)


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
            key: _to_json(value) for key, value in cast(dict[str, Any], obj).items()
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
            "node_errors": [],
            "chapter_digests": [],
            "scores": [],
            "verification": None,
            "output": None,
            "status": "running",
            "error": None,
            "model": model,
            "language": language,
        },
    )


def _run_graph(
    task_id: str | None,
    state: ActionState | None,
    mode: str = "full",
    *,
    action_type: str | None = None,
    decision: Any = None,  # noqa: ANN401 — whatever the paused node asked for
) -> dict[str, Any]:
    """Run the graph for this action, recording status on both sides of it.

    With checkpoints on, the run is thread ``task_id``: a retry or a
    redelivery of this task finds the steps it already finished and runs
    only the rest. The checkpoints go once the run has an outcome — they hold
    the thesis text, and nothing needs them after that.

    A run that pauses for the promoter (`interrupt`) is not an outcome: it is
    recorded as ``awaiting_input`` with what it has so far, its checkpoints
    stay, and a later call with ``state=None`` and the promoter's
    ``decision`` resumes it.
    """
    record_task_status(task_id, TaskStatus.RUNNING)
    kind = state["action_type"] if state is not None else action_type
    if kind is None:
        raise ValueError("a resumed run needs its action type")

    with open_checkpointer() as saver:
        if saver is None and state is not None:
            state = _without_pause(state)
        graph = build_action_graph(kind, mode=mode, checkpointer=saver)
        thread: RunnableConfig = (
            {"configurable": {"thread_id": task_id}} if saver and task_id else {}
        )
        saved = cast(dict[str, Any], graph.get_state(thread).values) if thread else {}
        if state is None and not saved:
            raise ValueError(f"nothing to resume for task {task_id}")
        meta = cast(dict[str, Any], state) if state is not None else saved
        config = run_config(
            action_type=kind,
            action_id=str(meta["action_id"]),
            student_id=str(meta["student_id"]),
            model=str(meta["model"]),
            task_id=task_id,
        )
        config.update(thread)
        meter = UsageMeter()
        callbacks = cast(list[BaseCallbackHandler], config.get("callbacks") or [])
        config["callbacks"] = [*callbacks, meter]

        pending = _pending_steps(graph, config) if thread else ()
        graph_input: Any
        if state is None:
            graph_input = Command(resume=decision)
        elif pending:
            logger.info("run_action.resuming", task_id=task_id, next=list(pending))
            graph_input = None
        else:
            graph_input = state
        try:
            result = _stream(graph, graph_input, config, task_id, pending)
            paused = bool(thread) and bool(graph.get_state(config).interrupts)
        finally:
            # Before the final status: `app` stops asking once the task is
            # over. A run that raised spent its tokens all the same.
            record_task_usage(task_id, meter.usage())
            flush_traces()
    payload = _result_payload(result)

    if paused:
        record_task_status(task_id, TaskStatus.AWAITING_INPUT, result=payload)
        return payload

    # Nodes never raise — they record the problem in state and let the graph
    # finish. The task failed when the node that produces the result did
    # (`error`), or when analysis failed and nothing came of it — a lone
    # `evaluate_methodology` whose one node broke. A review written despite
    # one broken branch is a result: it completes, and `node_errors` in the
    # payload says what it could not draw on.
    failure = _failure(result)
    if failure:
        record_task_status(task_id, TaskStatus.FAILED, result=payload, error=failure)
    else:
        record_task_status(task_id, TaskStatus.COMPLETED, result=payload)
    if task_id:
        delete_checkpoints([task_id])
    return payload


def _without_pause(state: ActionState) -> ActionState:
    """Drop the promoter's pause from a run that cannot be resumed.

    Without a checkpointer there is nowhere to keep the paused state; the
    run goes straight through, as it would have before the pause existed.
    """
    if not state["context"].get(PROMOTER_REVIEWS_FINDINGS):
        return state
    logger.warning("promoter_review_skipped_no_checkpointer")
    context = {**state["context"], PROMOTER_REVIEWS_FINDINGS: False}
    return cast(ActionState, {**state, "context": context})


def _pending_steps(
    graph: CompiledActionGraph, config: RunnableConfig
) -> tuple[str, ...]:
    """The steps an earlier attempt of this thread left unfinished, if any."""
    snapshot = graph.get_state(config)
    return tuple(snapshot.next)


def _steps(graph: CompiledActionGraph) -> list[str]:
    """The graph's own nodes, in the order they were added."""
    return [
        name for name in graph.get_graph().nodes if name not in ("__start__", "__end__")
    ]


def _stream(
    graph: CompiledActionGraph,
    state: Any,  # noqa: ANN401 — a fresh state, None, or a resume Command
    config: RunnableConfig,
    task_id: str | None,
    resuming: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Run the graph, recording each node as it finishes; return the final state.

    ``updates`` arrive once per finished node — the three parallel analyses
    one at a time, as each returns — and ``values`` carries the whole state
    after each step, the last of which is the result.

    ``state`` is None or a resume ``Command`` when continuing a thread: the
    checkpoint is the input. The steps before the first pending one count as
    done from the start — the graphs here add their nodes in the order they
    run.
    """
    steps = _steps(graph)
    first_pending = min((steps.index(n) for n in resuming if n in steps), default=0)
    done: list[str] = steps[:first_pending] if resuming else []
    final: dict[str, Any] = (
        dict(cast(dict[str, Any], state)) if isinstance(state, dict) else {}
    )
    record_task_progress(task_id, {"steps": steps, "done": list(done)})
    for mode, chunk in graph.stream(  # pyright: ignore[reportUnknownMemberType]
        state,  # type: ignore[arg-type]
        config=config,
        stream_mode=["updates", "values"],
    ):
        if mode == "values":
            final = dict(cast(dict[str, Any], chunk))
            continue
        finished = [n for n in cast(dict[str, Any], chunk) if n not in done]
        if finished:
            done.extend(finished)
            record_task_progress(task_id, {"steps": steps, "done": list(done)})
    return final


def _failure(result: dict[str, Any]) -> str | None:
    """Why this run produced nothing usable, or None if it did."""
    error = result.get("error")
    if error:
        return str(error)
    node_errors = cast(list[str], result.get("node_errors") or [])
    if node_errors and result.get("output") is None and not result.get("findings"):
        return "; ".join(node_errors)
    return None


def _record_final_failure(task: Task, task_id: str | None, exc: Exception) -> None:  # type: ignore[type-arg]
    """Persist a failure only when no retry is coming."""
    max_retries: int | None = task.max_retries
    if max_retries is not None and task.request.retries >= max_retries:
        problem = classify_provider_error(exc)
        record_task_status(
            task_id,
            TaskStatus.FAILED,
            error=str(problem or exc),
            error_code=problem.code if problem else None,
        )
        if task_id:
            delete_checkpoints([task_id])


def _may_run(task: Task, task_id: str | None) -> bool:  # type: ignore[type-arg]
    """Whether this delivery of the task should run at all.

    Not when its row is already finished: the promoter cancelled it, or the
    status poll gave it up as abandoned while the message was still on its
    way (`api.router.get_action_status`). Not when this attempt has been
    delivered too often: the run is what kills the worker, and it would kill
    the next one too. That one is failed here, with its checkpoints.
    """
    if not task_id:
        return True
    status = read_task_status(task_id)
    if status is not None and TaskStatus(status).is_terminal:
        logger.info("task_skipped_finished", task_id=task_id, status=status)
        return False
    deliveries = count_delivery(task.name, task_id, task.request.retries)
    if deliveries is not None and deliveries > _MAX_DELIVERIES:
        logger.error("task_delivered_too_often", task_id=task_id, times=deliveries)
        record_task_status(task_id, TaskStatus.FAILED, error=_KILLS_WORKER)
        delete_checkpoints([task_id])
        return False
    return True


def _fail_or_retry(task: Task, task_id: str | None, exc: Exception) -> NoReturn:  # type: ignore[type-arg]
    """Retry a failed run, unless retrying cannot help.

    No credits and a refused key fail the same way on every attempt, so the
    task fails at once and the promoter learns why in seconds, not after
    three retries a minute apart. A rate limit is worth waiting out, for as
    long as the provider asked; the checkpoints mean the retry picks up
    after the last finished step.
    """
    if isinstance(exc, SoftTimeLimitExceeded):
        # Whatever held it for half an hour would hold the retry too.
        record_task_status(task_id, TaskStatus.FAILED, error=_TIMED_OUT)
        if task_id:
            delete_checkpoints([task_id])
        raise exc
    problem = classify_provider_error(exc)
    if problem is not None and not problem.retryable:
        record_task_status(
            task_id, TaskStatus.FAILED, error=str(problem), error_code=problem.code
        )
        if task_id:
            delete_checkpoints([task_id])
        raise problem
    _record_final_failure(task, task_id, exc)
    countdown = problem.retry_after if problem is not None else None
    raise task.retry(exc=exc, countdown=countdown)


def _credentials(
    task_id: str | None, provider: str | None, sealed_api_key: str | None
) -> ModelCredentials | None:
    """Open the promoter's key, here in the worker that is about to use it.

    A key that will not open fails the task at once: retrying cannot fix it,
    and there is no other model to run on (ADR 0022).
    """
    if not (provider and sealed_api_key):
        return None
    try:
        return ModelCredentials(provider=provider, api_key=unseal(sealed_api_key))
    except KeyUnsealError as exc:
        record_task_status(task_id, TaskStatus.FAILED, error=str(exc))
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def run_action(
    self: Task,  # type: ignore[type-arg]
    action_id: str,
    action_type: str,
    student_id: str,
    context: dict[str, Any],
    # Unused: the provider decides the model. Still accepted, because a task
    # queued by an older `app` carries it.
    model: str | None = None,
    language: str = "pl",
    provider: str | None = None,
    sealed_api_key: str | None = None,
) -> dict[str, Any]:
    """Run one AI action for one student.

    `context` arrives fully assembled from `app` — the agent never calls back
    for data mid-task, so a worker's job never depends on `app` being up.

    The user's own provider key, when they brought one, arrives as its own
    argument, sealed for the broker (`key_transit`), and is opened and held
    only for the duration of the graph run. It is never put into the state,
    which is what gets serialised into the stored result.
    """
    task_id: str | None = self.request.id
    if not _may_run(self, task_id):
        return {}
    credentials = _credentials(task_id, provider, sealed_api_key)
    logger.info(
        "run_action.started",
        action_id=action_id,
        action_type=action_type,
        student_id=student_id,
        task_id=task_id,
        model=model_label(credentials),
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
                    context,
                    model_label(credentials),
                    language,
                ),
            )
        logger.info("run_action.completed", action_id=action_id)
        return payload
    except Exception as exc:
        logger.error("run_action.failed", action_id=action_id, error=str(exc))
        _fail_or_retry(self, task_id, exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def resume_action(
    self: Task,  # type: ignore[type-arg]
    action_type: str,
    decision: dict[str, Any],
    provider: str | None = None,
    sealed_api_key: str | None = None,
) -> dict[str, Any]:
    """Continue a run paused for the promoter, with their decision.

    Sent under the paused task's own id, so the thread, the status row and a
    cancel's revoke all still refer to the same thing. The key, when the
    promoter brought one, comes again: it was never stored.
    """
    task_id: str | None = self.request.id
    if not _may_run(self, task_id):
        return {}
    credentials = _credentials(task_id, provider, sealed_api_key)
    logger.info("resume_action.started", task_id=task_id, action_type=action_type)
    try:
        with use_credentials(credentials):
            return _run_graph(task_id, None, action_type=action_type, decision=decision)
    except Exception as exc:
        logger.error("resume_action.failed", task_id=task_id, error=str(exc))
        _fail_or_retry(self, task_id, exc)
