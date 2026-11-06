"""The terms version in `app` and the text the frontend shows must agree.

`app` decides who has accepted what; the frontend says which text they
read. A version bumped on one side only would let promoters accept a text
the gate does not know, or keep them out after accepting the one shown.
"""

import re
from pathlib import Path

import pytest

from src.identity.domain.terms import CURRENT_TERMS_VERSION

_FRONTEND_VERSION = (
    Path(__file__).resolve().parents[3] / "frontend/content/legal/version.ts"
)


def test_the_frontend_shows_the_version_in_force() -> None:
    if not _FRONTEND_VERSION.exists():  # e.g. inside the `app` image
        pytest.skip("no frontend next to this checkout")
    found = re.search(
        r'TERMS_VERSION = "([^"]+)"', _FRONTEND_VERSION.read_text(encoding="utf-8")
    )
    assert found is not None
    assert found.group(1) == CURRENT_TERMS_VERSION
