"""Reading JSON back out of a chat model's reply.

Every action asks the model for JSON and every action has to cope with the
same two habits: wrapping the answer in a markdown fence, and returning
content as a list of parts (reasoning, then text) rather than a string.
Parsing and validating what is left is `structured.invoke_structured`'s job.
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
    """Render a chat message's content as a string.

    A hosted model answers in parts — its reasoning first, then the text —
    and only the text is the reply: Claude's thinking block, serialised along
    with the rest, turned a valid JSON answer into a list no schema accepts.
    Content with no text part at all (a tool's structured result) is still
    rendered whole.
    """
    if isinstance(content, str):
        return content
    texts: list[str] = []
    for part in content:
        if isinstance(part, str):
            texts.append(part)
        elif isinstance(part, dict):
            block = cast(dict[str, Any], part)
            if block.get("type") == "text" and isinstance(block.get("text"), str):
                texts.append(block["text"])
    return "".join(texts) if texts else json.dumps(content)
