"""Asking a chat model for JSON of a known shape, and getting it.

Before this, every node did ``llm.invoke`` → ``json.loads`` and hoped. A
model that closed a bracket too early, called a key ``criterion`` instead of
``criteria`` or wrote "Major" for "major" cost the whole branch: the node
logged a parse error and the review went ahead without it.

Three layers, cheapest first:

1. **The provider's structured outputs.** The reply's JSON schema goes with
   the request as ``response_format``; LangChain hands it to Anthropic as
   ``output_config.format`` and to OpenAI as it is. Claude then decodes only
   tokens that keep the reply valid against it. Only for shapes whose root is
   an object: OpenAI takes nothing else, and a list of findings stays a list
   rather than a prompt that says one thing and a schema that says another.
2. **Validation** against a Pydantic model, always. Valid JSON can still be
   the wrong JSON — a list of findings is not constrained, and OpenAI's
   non-strict mode is a strong hint, not a guarantee.
3. **Repair**: when validation fails, the model is shown its own reply and the
   validation error, and asked once more. Cheaper than failing the branch,
   and the error message is usually all it needed.

The prompts still describe the shape in words: they explain to the model
*why* a field is there, which a schema does not.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any, cast

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage
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


_NAME = re.compile(r"[^a-zA-Z0-9_-]")


def response_format(shape: TypeAdapter[Any], node: str) -> dict[str, Any] | None:
    """The schema to send with the request, or None to leave the reply free.

    Not strict on OpenAI: strict mode wants every property required, and the
    replies have optional keys. Claude's structured outputs have no such mode.
    """
    schema = shape.json_schema()
    if schema.get("type") != "object":
        return None
    return {
        "type": "json_schema",
        "json_schema": {
            "name": _NAME.sub("_", node),
            "schema": schema,
            "strict": False,
        },
    }


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
    constrained = response_format(shape, node)
    if constrained is not None:
        kwargs["response_format"] = constrained

    conversation = list(messages)
    last_error: Exception | None = None
    for attempt in range(1, _ATTEMPTS + 1):
        response = llm.invoke(conversation, **kwargs)
        metadata = cast(dict[str, Any], response.response_metadata)  # pyright: ignore[reportUnknownMemberType]
        if metadata.get("stop_reason") == "refusal":
            # A hosted model's safety classifier declined; asking again with
            # "fix your JSON" would only be declined again.
            raise StructuredOutputError("the model declined to answer this request")
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
            # The reply goes back exactly as it came, reasoning parts and
            # all: Claude checks that a turn it is shown again is the turn it
            # wrote, and a copy rebuilt from the text alone is not.
            conversation = [
                *conversation,
                response,
                HumanMessage(content=_REPAIR_PROMPT.format(error=_format_error(exc))),
            ]
    raise StructuredOutputError(
        f"no valid reply after {_ATTEMPTS} attempts: {last_error}"
    )
