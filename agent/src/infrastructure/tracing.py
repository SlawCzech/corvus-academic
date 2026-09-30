"""Tracing of graph runs — which node asked the model what, and how long it took.

Langfuse, self-hosted (infra/langfuse), hooked in as a LangChain callback. The
callback is attached once, to the graph run's config; LangGraph hands that
config down to every node, and every ``llm.invoke`` inside a node picks it up
from the context. No node knows it is being traced.

Off unless configured: a missing base URL or key pair means no callback at
all, not a callback that fails on every call.

What is traced is what the model sees: prompts carry thesis text, which is why
the target is a Langfuse on the same machine and not a SaaS. The user's own
provider key never reaches a trace — it is held in a ContextVar by
`llm_factory` and is not part of any prompt, state or config.
"""

from functools import lru_cache
from typing import Any

import structlog
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableConfig

from src.infrastructure.settings import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def tracing_enabled() -> bool:
    """Whether a Langfuse to send traces to is configured."""
    return bool(
        settings.langfuse_base_url
        and settings.langfuse_public_key
        and settings.langfuse_secret_key
    )


@lru_cache(maxsize=1)
def _client() -> Any:  # noqa: ANN401 — langfuse ships no stubs worth the name
    """The process-wide Langfuse client, created on first use.

    Imported lazily so a worker with tracing off never loads the SDK and its
    OpenTelemetry exporter.
    """
    from langfuse import Langfuse

    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        base_url=settings.langfuse_base_url,
    )


def _callbacks() -> list[BaseCallbackHandler]:
    if not tracing_enabled():
        return []
    try:
        from langfuse.langchain import CallbackHandler

        _client()
        return [CallbackHandler(public_key=settings.langfuse_public_key)]
    except Exception as exc:
        # Tracing is for whoever tunes prompts; an action must never fail
        # because the tracing server is down or misconfigured.
        logger.warning("tracing_unavailable", error=str(exc))
        return []


def run_config(
    *,
    action_type: str,
    action_id: str,
    student_id: str,
    model: str,
    task_id: str | None,
) -> RunnableConfig:
    """The config one graph run is invoked with.

    The student is the Langfuse *session*, so every action ever run for one
    student lines up in one view — the history of what the AI told their
    promoter. Tags carry what traces are filtered by: action type and model.
    """
    return RunnableConfig(
        run_name=f"action:{action_type}",
        callbacks=_callbacks(),
        tags=[action_type, model],
        metadata={
            "action_id": action_id,
            "task_id": task_id,
            "model": model,
            "langfuse_session_id": student_id,
            "langfuse_tags": [action_type, model],
        },
    )


def flush() -> None:
    """Send what is buffered before the task returns.

    The SDK exports in the background. A Celery worker process outlives the
    task, so nothing is lost in the long run — but a trace that turns up a
    minute after the action finished is a trace nobody finds.
    """
    if not tracing_enabled():
        return
    try:
        _client().flush()
    except Exception as exc:
        logger.warning("tracing_flush_failed", error=str(exc))
