"""Asking a chat model for JSON of a known shape, and getting it.

Before this, every node did ``llm.invoke`` → ``json.loads`` and hoped. A local
model that closed a bracket too early, called a key ``criterion`` instead of
``criteria`` or wrote "Major" for "major" cost the whole branch: the node
logged a parse error and the review went ahead without it.

Three layers, cheapest first:

1. **Constrained decoding** where the backend has it. Ollama takes a JSON
   schema as ``format`` and samples only tokens that keep the output valid
   against it — malformed JSON stops being possible rather than unlikely.
2. **Validation** against a Pydantic model, on every backend. Valid JSON can
   still be the wrong JSON: a missing key, a severity outside the three.
3. **Repair**: when validation fails, the model is shown its own reply and the
   validation error, and asked once more. Cheaper than failing the branch,
   and the error message is usually all it needed.

The prompts still describe the shape in words. The schema makes it binding on
Ollama; the words are what a hosted model follows, and what explains to any
model *why* a field is there.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_ollama import ChatOllama
from pydantic import TypeAdapter, ValidationError

from src.application.json_output import extract_json, message_text

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# One repair turn. A model that cannot fix its reply after being shown the
# error rarely fixes it on the third try either; the branch fails and says so.
_ATTEMPTS = 2

_REPAIR_PROMPT = """Your previous reply could not be used:

{error}

Reply again with ONLY the corrected JSON — same content, fixed to match the \
required format. No markdown, no explanation."""


class StructuredOutputError(ValueError):
    """The model's reply never matched the required shape."""


def _format_error(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        # The first few problems, located — "scores.2.points: Input should be
        # a valid integer" is something a model can act on.
        return "\n".join(
            f"- {'.'.join(str(p) for p in err['loc']) or '(root)'}: {err['msg']}"
            for err in exc.errors()[:5]
        )
    return f"- not valid JSON: {exc}"


def invoke_structured[T](
    llm: BaseChatModel,
    messages: Sequence[BaseMessage],
    shape: TypeAdapter[T],
    *,
    node: str,
) -> T:
    """Invoke the model and return its reply parsed into ``shape``.

    Raises `StructuredOutputError` when every attempt fails; nodes catch it
    like any other failure and report it in state.
    """
    kwargs: dict[str, Any] = {}
    if isinstance(llm, ChatOllama):
        kwargs["format"] = shape.json_schema()

    conversation = list(messages)
    last_error: Exception | None = None
    for attempt in range(1, _ATTEMPTS + 1):
        response = llm.invoke(conversation, **kwargs)
        raw = message_text(response.content)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        try:
            return shape.validate_json(extract_json(raw))
        except (ValidationError, ValueError) as exc:
            last_error = exc
            logger.warning(
                "structured_output_invalid",
                node=node,
                attempt=attempt,
                error=_format_error(exc)[:500],
            )
            conversation = [
                *conversation,
                AIMessage(content=raw),
                HumanMessage(content=_REPAIR_PROMPT.format(error=_format_error(exc))),
            ]
    raise StructuredOutputError(
        f"no valid reply after {_ATTEMPTS} attempts: {last_error}"
    )
