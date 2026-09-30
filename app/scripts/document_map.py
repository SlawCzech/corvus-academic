"""Print the document map `app` would send with an action, for a text file.

    uv run python scripts/document_map.py thesis.md > document_map.json

The map is what every AI action gets alongside the thesis text (see
`src/document/outline.py`); the agent's evals keep one per case so their runs
see the thesis the way production does.
"""

import json
import sys
from pathlib import Path

from src.document.outline import outline_payload


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: document_map.py <text file>")
    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    print(json.dumps(outline_payload(text), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
