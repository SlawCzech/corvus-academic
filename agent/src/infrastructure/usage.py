"""Count the tokens one action spends, per model, across all its calls.

A callback on the graph run sees every chat-model call the nodes make — the
parallel analyses, a digest per chapter, each turn of the bibliography agent,
a repair turn — because LangChain passes the run's callbacks down to every
model invoked inside a node. Nodes stay unaware of it.

What is counted is what the provider reports in ``usage_metadata``; on a
hosted model that is what the promoter's account is billed for. Thinking
tokens are part of ``output_tokens``. Embeddings are not counted: they run on
the local model and cost nothing on anyone's account.
"""

import threading
from typing import Any, TypedDict, cast

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult


class TokenCounts(TypedDict):
    input_tokens: int
    output_tokens: int
    total_tokens: int


class Usage(TypedDict):
    """Totals, and the same split by model — the shape stored with a task."""

    input_tokens: int
    output_tokens: int
    total_tokens: int
    by_model: dict[str, TokenCounts]


_COUNTS = ("input_tokens", "output_tokens", "total_tokens")


class UsageMeter(BaseCallbackHandler):
    """A callback that adds up ``usage_metadata`` of every chat-model reply.

    Thread-safe: LangGraph runs parallel branches in threads that share the
    run's callbacks.
    """

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._by_model: dict[str, TokenCounts] = {}

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:  # noqa: ANN401
        for generations in response.generations:
            for generation in generations:
                if not isinstance(generation, ChatGeneration):
                    continue
                message = generation.message
                if not isinstance(message, AIMessage) or not message.usage_metadata:
                    continue
                meta = cast(
                    dict[str, Any],
                    message.response_metadata,  # pyright: ignore[reportUnknownMemberType]
                )
                # A reply without a model name still cost tokens: count it.
                name = str(meta.get("model_name") or meta.get("model") or "unknown")
                counts = cast(dict[str, Any], message.usage_metadata)
                self._add(name, counts)

    def _add(self, name: str, counts: dict[str, Any]) -> None:
        with self._lock:
            current = self._by_model.setdefault(
                name, TokenCounts(input_tokens=0, output_tokens=0, total_tokens=0)
            )
            for key in _COUNTS:
                current[key] += int(counts.get(key) or 0)

    def usage(self) -> Usage | None:
        """What was counted so far; None when no call reported any usage."""
        with self._lock:
            if not self._by_model:
                return None
            by_model = {name: TokenCounts(**c) for name, c in self._by_model.items()}
        return _with_totals(by_model)


def merge_usage(earlier: Any, later: Usage) -> Usage:  # noqa: ANN401 — a stored JSON value
    """Add ``later`` to a previously stored usage, model by model.

    A paused review resumed, or a retry after a crash, is a second run under
    the same task: what the action cost is the sum of both.
    """
    by_model: dict[str, TokenCounts] = {
        name: TokenCounts(**counts) for name, counts in later["by_model"].items()
    }
    if isinstance(earlier, dict):
        stored = cast(dict[str, Any], earlier).get("by_model")
        if isinstance(stored, dict):
            for name, counts in cast(dict[str, dict[str, Any]], stored).items():
                current = by_model.setdefault(
                    name, TokenCounts(input_tokens=0, output_tokens=0, total_tokens=0)
                )
                for key in _COUNTS:
                    current[key] += int(counts.get(key) or 0)
    return _with_totals(by_model)


def _with_totals(by_model: dict[str, TokenCounts]) -> Usage:
    return Usage(
        input_tokens=sum(c["input_tokens"] for c in by_model.values()),
        output_tokens=sum(c["output_tokens"] for c in by_model.values()),
        total_tokens=sum(c["total_tokens"] for c in by_model.values()),
        by_model=by_model,
    )
