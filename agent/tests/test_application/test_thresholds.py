"""Tests for the numbers code compares and the model is told.

A wrong standing here is worse than none: the block tells the model not to
recount, so it would repeat the mistake as a finding.
"""

from typing import Any

import pytest

from src.application.thresholds import render_threshold_block

_THRESHOLDS = {
    "min_sources": 25,
    "min_foreign_sources": 4,
    "min_body_chars": 80_000,
    "max_body_chars": 130_000,
}


def _ctx(**document_map: int | None) -> dict[str, Any]:
    return {"thresholds": _THRESHOLDS, "document_map": document_map}


def test_no_thresholds_no_block() -> None:
    assert render_threshold_block({"document_map": {"body_chars": 90_000}}) == ""


def test_thresholds_of_nothing_no_block() -> None:
    assert render_threshold_block({"thresholds": {"min_sources": None}}) == ""


@pytest.mark.parametrize(
    ("entries", "web", "standing"),
    [
        (22, 0, "22 entries, at least 25 required: BELOW the minimum."),
        (30, 8, "meets the minimum only if the entries with a web address count."),
        (30, 5, "30 entries, at least 25 required: meets the minimum."),
        (25, 0, "25 entries, at least 25 required: meets the minimum."),
    ],
)
def test_sources_against_the_minimum(entries: int, web: int, standing: str) -> None:
    block = render_threshold_block(
        _ctx(bibliography_entries=entries, bibliography_web_entries=web)
    )

    assert standing in block


def test_web_entries_are_named_as_possible_netography() -> None:
    block = render_threshold_block(
        _ctx(bibliography_entries=9, bibliography_web_entries=7)
    )

    assert "7 of them give a web address, so they may be netography" in block


def test_a_map_from_before_the_web_count_reads_as_none() -> None:
    block = render_threshold_block(_ctx(bibliography_entries=30))

    assert "meets the minimum." in block
    assert "web address" not in block


def test_no_bibliography_is_said_not_counted_as_zero() -> None:
    block = render_threshold_block(_ctx(bibliography_entries=None))

    assert "Code found no bibliography to count." in block
    assert "BELOW" not in block


def test_foreign_sources_are_left_to_the_model() -> None:
    block = render_threshold_block(_ctx())

    assert "at least 4 required. Not counted by code" in block


@pytest.mark.parametrize(
    ("body", "standing"),
    [
        (79_999, "below the range"),
        (80_000, "within the range"),
        (130_000, "within the range"),
        (130_001, "above the range"),
    ],
)
def test_length_against_the_range(body: int, standing: str) -> None:
    block = render_threshold_block(_ctx(body_chars=body))

    assert f"against 80,000–130,000: {standing}." in block


def test_a_body_that_could_not_be_measured_is_said() -> None:
    block = render_threshold_block(_ctx(body_chars=None))

    assert "Code could not measure the body." in block


def test_a_minimum_length_alone_has_no_upper_bound() -> None:
    block = render_threshold_block(
        {
            "thresholds": {"min_body_chars": 50_000},
            "document_map": {"body_chars": 90_000},
        }
    )

    assert "against at least 50,000: within the range." in block


def test_the_rule_leaves_the_severity_to_the_model() -> None:
    block = render_threshold_block(_ctx())

    assert "They are not findings." in block
    assert "a suggested length is not a hard limit" in block
