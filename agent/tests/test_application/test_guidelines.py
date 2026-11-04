"""Tests for the guidelines loader."""

from src.application.guidelines import get_guidelines_path, load_guidelines
from src.domain.analysis import ThesisType


def test_load_guidelines_bachelor_returns_nonempty_string() -> None:
    """Bachelor guidelines file loads and is non-empty."""
    content = load_guidelines(ThesisType.BACHELOR)
    assert isinstance(content, str)
    assert len(content) > 100


def test_load_guidelines_master_article_returns_nonempty_string() -> None:
    """Master article guidelines file loads and is non-empty."""
    content = load_guidelines(ThesisType.MASTER_ARTICLE)
    assert isinstance(content, str)
    assert len(content) > 100


def test_load_guidelines_raises_for_unknown_thesis_type() -> None:
    """Unknown thesis_type raises ValueError."""
    import pytest

    with pytest.raises(ValueError, match="No guidelines file"):
        load_guidelines("phd")


def test_load_guidelines_is_cached() -> None:
    """Second call returns the exact same object (lru_cache hit)."""
    first = load_guidelines(ThesisType.BACHELOR)
    second = load_guidelines(ThesisType.BACHELOR)
    assert first is second


def test_guidelines_bachelor_contains_critical_section() -> None:
    """Bachelor guidelines include a CRITICAL severity section (smoke test)."""
    content = load_guidelines(ThesisType.BACHELOR)
    assert "CRITICAL" in content


def test_guidelines_master_contains_critical_section() -> None:
    """Master guidelines include a CRITICAL severity section (smoke test)."""
    content = load_guidelines(ThesisType.MASTER_ARTICLE)
    assert "CRITICAL" in content


def test_get_guidelines_path_bachelor_exists() -> None:
    """get_guidelines_path returns a Path that actually exists on disk."""
    path = get_guidelines_path(ThesisType.BACHELOR)
    assert path.exists()


def test_get_guidelines_path_master_exists() -> None:
    """get_guidelines_path returns a Path that actually exists on disk."""
    path = get_guidelines_path(ThesisType.MASTER_ARTICLE)
    assert path.exists()


def test_get_guidelines_path_raises_for_unknown_type() -> None:
    """get_guidelines_path raises ValueError for unknown thesis type."""
    import pytest

    with pytest.raises(ValueError, match="No guidelines file"):
        get_guidelines_path("unknown")
