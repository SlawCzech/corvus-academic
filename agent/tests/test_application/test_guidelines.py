"""Tests for the guidelines loader, chunker and retrieval."""

from unittest.mock import patch

from src.application.guidelines import (
    get_guidelines_path,
    load_guidelines,
    retrieve_relevant_guidelines,
    split_into_chunks,
)
from src.domain.analysis import ThesisType
from src.infrastructure.guideline_store import StoredChunk


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


# ---------- chunking ----------


def test_chunks_follow_the_documents_own_sections() -> None:
    """Split on headings, not on a character count: these are numbered rules."""
    chunks = split_into_chunks(load_guidelines(ThesisType.BACHELOR))

    headings = [c.section for c in chunks]
    assert "0. Preamble" in headings
    assert any(h.startswith("1. Required Structure") for h in headings)
    assert all(c.text.strip() for c in chunks)


def test_every_chunk_keeps_its_heading() -> None:
    """A rule retrieved without its number is a rule nobody can cite."""
    chunks = split_into_chunks(load_guidelines(ThesisType.MASTER_ARTICLE))

    for chunk in chunks[1:]:
        assert chunk.text.startswith("## ")
        # Subsections carry their parent heading first, then their own.
        parent = chunk.section.split(" / ")[0]
        assert parent in chunk.text.splitlines()[0]


def test_long_sections_are_split_by_subsection() -> None:
    """§1 covers a dozen unrelated requirements; retrieving it whole retrieves
    everything, and then the search means nothing."""
    chunks = split_into_chunks(load_guidelines(ThesisType.BACHELOR))

    structure = [c for c in chunks if c.section.startswith("1. Required Structure")]
    assert len(structure) > 5
    assert any("1.4 Introduction" in c.section for c in structure)
    # Each subsection still says which section it belongs to.
    intro = next(c for c in structure if "1.4 Introduction" in c.section)
    assert intro.text.startswith("## 1. Required Structure")
    assert "### 1.4 Introduction" in intro.text


def test_the_severity_section_is_never_split() -> None:
    """Half a rulebook retrieved is worse than none of it."""
    chunks = split_into_chunks(load_guidelines(ThesisType.MASTER_ARTICLE))

    pinned = [c for c in chunks if c.always_include]
    assert len(pinned) == 1
    assert "/" not in pinned[0].section
    assert len(pinned[0].text) > 1000


def test_severity_rules_are_always_included() -> None:
    """Drop them and every finding becomes a guess at what 'critical' means."""
    for thesis_type in (ThesisType.BACHELOR, ThesisType.MASTER_ARTICLE):
        chunks = split_into_chunks(load_guidelines(thesis_type))
        pinned = [c for c in chunks if c.always_include]
        assert len(pinned) == 1
        assert "Severity" in pinned[0].section


def test_ordinary_sections_are_not_pinned() -> None:
    chunks = split_into_chunks(load_guidelines(ThesisType.BACHELOR))
    structure = next(c for c in chunks if c.section.startswith("1."))
    assert structure.always_include is False


def test_empty_document_yields_no_chunks() -> None:
    assert split_into_chunks("   ") == []


# ---------- retrieval ----------

_THESIS = "Rozdział 1: Wstęp. Celem pracy jest analiza instytucji."


def test_retrieval_returns_the_matching_sections() -> None:
    stored = [
        StoredChunk(section="4. Severity", text="## 4. Severity rules"),
        StoredChunk(section="1. Structure", text="## 1. Required structure"),
    ]
    with (
        patch("src.application.guidelines.embed_query", return_value=[0.1, 0.2]),
        patch(
            "src.application.guidelines.search_chunks", return_value=stored
        ) as search,
    ):
        result = retrieve_relevant_guidelines(ThesisType.BACHELOR, _THESIS)

    assert "## 4. Severity rules" in result
    assert "## 1. Required structure" in result
    # Retrieval runs against the opening of the thesis, not the whole file.
    assert search.call_args.args[0] == ThesisType.BACHELOR


def test_retrieval_falls_back_to_the_file_when_nothing_is_ingested() -> None:
    """A database nobody ran the ingestion against must not break an action."""
    with (
        patch("src.application.guidelines.embed_query", return_value=[0.1]),
        patch("src.application.guidelines.search_chunks", return_value=[]),
    ):
        result = retrieve_relevant_guidelines(ThesisType.BACHELOR, _THESIS)

    assert result == load_guidelines(ThesisType.BACHELOR)


def test_retrieval_falls_back_when_the_embedder_is_unreachable() -> None:
    """No embedding model pulled is a degraded prompt, not a failed action."""
    with patch(
        "src.application.guidelines.embed_query",
        side_effect=Exception("model 'nomic-embed-text' not found"),
    ):
        result = retrieve_relevant_guidelines(ThesisType.BACHELOR, _THESIS)

    assert result == load_guidelines(ThesisType.BACHELOR)


def test_retrieval_without_a_thesis_uses_the_whole_document() -> None:
    """There is nothing to retrieve against before a draft exists."""
    with patch("src.application.guidelines.embed_query") as embed:
        result = retrieve_relevant_guidelines(ThesisType.BACHELOR, "   ")

    embed.assert_not_called()
    assert result == load_guidelines(ThesisType.BACHELOR)
