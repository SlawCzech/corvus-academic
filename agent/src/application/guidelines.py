"""University requirements the agent falls back on.

A student with a guideline set gets its rubric from `app`; these files are
for everyone else. They go into the prompt whole: a few kilobytes are nothing
to a hosted model, and the severity rules only make sense next to the rest.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from src.domain.analysis import ThesisType

_GUIDELINES_DIR = Path(__file__).parent / "prompts" / "guidelines"

_GUIDELINES_FILES: dict[str, str] = {
    ThesisType.BACHELOR: "university_requirements_bachelor.md",
    ThesisType.MASTER_ARTICLE: "university_requirements_master_article.md",
}


@lru_cache(maxsize=4)
def load_guidelines(thesis_type: str) -> str:
    """Load university requirements for the given thesis type.

    Cached after first load — file is read once per process lifetime.
    Raises ValueError for unknown thesis types, FileNotFoundError if missing.
    """
    filename = _GUIDELINES_FILES.get(thesis_type)
    if filename is None:
        raise ValueError(f"No guidelines file for thesis type: {thesis_type!r}")
    path = _GUIDELINES_DIR / filename
    return path.read_text(encoding="utf-8")


def get_guidelines_path(thesis_type: str) -> Path:
    """Return the resolved path to the guidelines file (for testing)."""
    filename = _GUIDELINES_FILES.get(thesis_type)
    if filename is None:
        raise ValueError(f"No guidelines file for thesis type: {thesis_type!r}")
    return _GUIDELINES_DIR / filename
