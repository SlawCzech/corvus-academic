"""Tests for what a node is shown of a thesis: all of it, plus the counts.

A model reads headings for itself but miscounts characters and bibliography
entries, which is how a thesis with 41 entries once got reported as having 7.
The counts `app` computes therefore travel with the text.
"""

from typing import Any

from src.application.excerpt import render_document_block

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
    ],
}


def _ctx() -> dict[str, Any]:
    return {"text": _THESIS, "document_map": _MAP}


def test_the_thesis_is_shown_complete() -> None:
    block = render_document_block(_ctx())

    assert f"## Thesis, complete ({len(_THESIS):,} characters)" in block
    assert _THESIS in block


def test_the_counts_travel_with_the_text() -> None:
    block = render_document_block(_ctx())

    assert "Bibliography entries counted: 41." in block
    assert "Length of the thesis body: 28,000 characters" in block


def test_web_entries_are_counted_when_there_are_some() -> None:
    ctx = {"text": "x", "document_map": {**_MAP, "bibliography_web_entries": 3}}

    assert "41, of which 3 give a web address." in render_document_block(ctx)


def test_the_outline_is_not_repeated() -> None:
    """With the text complete, a list of headings and offsets is only one
    more thing that can be wrong."""
    block = render_document_block(_ctx())

    assert "Sections present, in order" not in block
    assert "Metodyka badań (char" not in block


def test_a_context_without_a_map_gets_the_text_alone() -> None:
    block = render_document_block({"text": _THESIS})

    assert _THESIS in block
    assert "Counted from the thesis" not in block


def test_an_empty_context_does_not_raise() -> None:
    assert render_document_block({}) is not None
