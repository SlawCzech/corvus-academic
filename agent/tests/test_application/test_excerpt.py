"""Tests for what a node is shown of a thesis, and told about the rest.

These guard the bug that made a whole review false: the nodes read the first
part of a thesis, never saw the methodology chapter on page 18, and reported
it as never written. The excerpt block is what carries the document map into
the prompt, so what matters here is that the map survives the truncation and
that the rules travel with it.
"""

from typing import Any

from src.application.excerpt import reading_budget, render_document_block
from src.infrastructure.llm_factory import ModelCredentials, use_credentials

_THESIS = "Wstęp. " * 5000  # 35 000 characters

_MAP: dict[str, Any] = {
    "total_chars": len(_THESIS),
    "body_chars": 28000,
    "bibliography_entries": 41,
    "sections": [
        {"title": "Wstęp", "canonical": "introduction", "start": 0, "char_count": 900},
        {
            "title": "Metodyka badań",
            "canonical": "methodology",
            "start": 30000,
            "char_count": 5000,
        },
        {
            "title": "Bibliografia:",
            "canonical": "bibliography",
            "start": 34000,
            "char_count": 1000,
        },
    ],
}


def _ctx() -> dict[str, Any]:
    return {"text": _THESIS, "document_map": _MAP}


def test_sections_outside_the_excerpt_are_still_named() -> None:
    block = render_document_block(_ctx(), head_chars=1000)

    assert "Metodyka badań" in block
    assert "char 30,000" in block


def test_the_excerpt_says_how_much_of_the_thesis_it_is() -> None:
    block = render_document_block(_ctx(), head_chars=1000)

    assert "characters 0–1,000 of 35,000" in block
    assert "NOT shown" in block


def test_truncation_brings_the_rules_that_stop_false_findings() -> None:
    block = render_document_block(_ctx(), head_chars=1000)

    assert "NEVER report a section as missing" in block
    assert "Bibliography entries counted: 41" in block


def test_length_is_reported_as_the_body_not_the_extracted_total() -> None:
    """The 55-65k limit is about the article; the total carries a title page,
    declarations, a table of contents and a bibliography on top of it."""
    block = render_document_block(_ctx(), head_chars=1000)

    assert "Length of the thesis body: 28,000" in block
    assert "Judge length against the body length" in block


def test_a_thesis_that_fits_gets_no_truncation_warning() -> None:
    """Nothing was withheld, so nothing should be said about withholding."""
    block = render_document_block(_ctx(), head_chars=len(_THESIS) + 1)

    assert "NOT shown" not in block
    assert "NEVER report a section as missing" not in block
    assert "Thesis, complete" in block


def test_the_bibliography_is_appended_when_the_excerpt_stops_short_of_it() -> None:
    """Judging sources on what the excerpt happened to include is how a thesis
    with 41 entries got reported as having 7."""
    block = render_document_block(_ctx(), head_chars=1000)

    assert "## Bibliography (characters 34,000" in block


def test_the_bibliography_is_not_repeated_when_the_excerpt_covers_it() -> None:
    block = render_document_block(_ctx(), head_chars=len(_THESIS))

    assert "## Bibliography (characters" not in block


def test_a_node_that_asks_not_to_see_the_bibliography_does_not_get_it() -> None:
    block = render_document_block(_ctx(), head_chars=1000, include_bibliography=False)

    assert "## Bibliography (characters" not in block


def test_a_context_without_a_map_still_gets_the_text_and_a_warning() -> None:
    """Older actions and unmapped documents must not lose the excerpt itself."""
    block = render_document_block({"text": _THESIS}, head_chars=1000)

    assert _THESIS[:1000] in block
    assert "Document map" not in block
    assert "NOT shown" in block


def test_an_empty_context_does_not_raise() -> None:
    assert render_document_block({}, head_chars=1000) is not None


# ---------- a hosted model reads the whole thesis ----------

_HOSTED = ModelCredentials(provider="claude", api_key="k")


def test_the_local_model_is_rationed_and_a_hosted_one_is_not() -> None:
    assert reading_budget(7000) == 7000
    with use_credentials(_HOSTED):
        assert reading_budget(7000) is None
    # Back on the service's own model once the promoter's key is out of scope.
    assert reading_budget(7000) == 7000


def test_a_hosted_model_is_shown_the_thesis_complete() -> None:
    with use_credentials(_HOSTED):
        block = render_document_block(_ctx(), head_chars=1000)

    assert f"## Thesis, complete ({len(_THESIS):,} characters)" in block
    assert _THESIS in block
    # The map still travels with it: the counts in it are computed, not read.
    assert "Bibliography entries counted: 41." in block
    # No excerpt, so nothing to warn about — and no second copy of the list.
    assert "What this excerpt does and does not prove" not in block
    assert "NOT shown" not in block
    assert block.count("## Bibliography (characters") == 0
