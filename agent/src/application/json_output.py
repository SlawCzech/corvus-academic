"""Reading JSON back out of a chat model's reply.

Every action asks the model for JSON and every action has to cope with the
same two habits: wrapping the answer in a markdown fence, and returning
content as a list of parts rather than a string. This was copied into four
node files before it became one.
"""

import json
import re
from collections.abc import Sequence
from typing import Any, cast

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def extract_json(text: str) -> str:
    """Strip a markdown code fence if the model wrapped its JSON in one."""
    match = _FENCE_RE.search(text)
    return match.group(1) if match else text.strip()


def message_text(content: str | Sequence[object]) -> str:
    """Render a chat message's content as a string."""
    return content if isinstance(content, str) else json.dumps(content)


def parse_json_object(content: str | Sequence[object]) -> dict[str, Any]:
    """Parse a model reply expected to be a JSON object."""
    data: Any = json.loads(extract_json(message_text(content)))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object, got {type(data).__name__}")
    return cast(dict[str, Any], data)


def parse_json_array(content: str | Sequence[object]) -> list[Any]:
    """Parse a model reply expected to be a JSON array."""
    data: Any = json.loads(extract_json(message_text(content)))
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array, got {type(data).__name__}")
    return cast(list[Any], data)


def as_list(value: Any) -> list[Any]:  # noqa: ANN401
    """Coerce a model-supplied field to a list, tolerating a missing key.

    Models drop keys, or return null where an array was asked for; every node
    would otherwise repeat the same `or []` dance.
    """
    return cast(list[Any], value) if isinstance(value, list) else []
