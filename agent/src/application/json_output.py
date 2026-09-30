"""Reading JSON back out of a chat model's reply.

Every action asks the model for JSON and every action has to cope with the
same two habits: wrapping the answer in a markdown fence, and returning
content as a list of parts rather than a string. Parsing and validating what
is left is `structured.invoke_structured`'s job.
"""

import json
import re
from collections.abc import Sequence

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def extract_json(text: str) -> str:
    """Strip a markdown code fence if the model wrapped its JSON in one."""
    match = _FENCE_RE.search(text)
    return match.group(1) if match else text.strip()


def message_text(content: str | Sequence[object]) -> str:
    """Render a chat message's content as a string."""
    return content if isinstance(content, str) else json.dumps(content)
