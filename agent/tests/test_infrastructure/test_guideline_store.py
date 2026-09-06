"""Tests for reading guideline chunks from synchronous worker code."""

from unittest.mock import patch

from src.infrastructure.guideline_store import StoredChunk, search_chunks


def test_search_returns_what_the_repository_found() -> None:
    found = [StoredChunk(section="4. Severity", text="## 4. Severity rules")]
    with patch("src.infrastructure.guideline_store._search", return_value=found):
        assert search_chunks("bachelor", [0.1], "nomic-embed-text", 4) == found


def test_a_database_failure_is_not_an_action_failure() -> None:
    """Retrieval that cannot run falls back to the file, one level up."""
    with patch(
        "src.infrastructure.guideline_store._search",
        side_effect=OSError("db down"),
    ):
        assert search_chunks("bachelor", [0.1], "nomic-embed-text", 4) == []
