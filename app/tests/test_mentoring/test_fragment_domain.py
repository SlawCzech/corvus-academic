"""Unit tests for the fragment entities."""

import uuid
from datetime import UTC, date, datetime

import pytest

from src.mentoring.domain.fragment import (
    FragmentVerdict,
    PartState,
    ThesisFragment,
    ThesisPart,
    part_state,
)

_AT = datetime(2026, 10, 31, tzinfo=UTC)


def _fragment(**fields: object) -> ThesisFragment:
    values: dict[str, object] = {
        "id": uuid.uuid4(),
        "student_id": uuid.uuid4(),
        "part_id": uuid.uuid4(),
        "round_number": 1,
        "received_on": date(2026, 10, 28),
        "text": "Rozdział o metodologii.",
        "format": "text",
        "uploaded_by": uuid.uuid4(),
    }
    return ThesisFragment(**(values | fields))  # type: ignore[arg-type]


def test_a_part_needs_a_name() -> None:
    with pytest.raises(ValueError, match="name"):
        ThesisPart(id=uuid.uuid4(), student_id=uuid.uuid4(), name="  ", position=1)


def test_a_fragment_needs_text_and_a_round() -> None:
    with pytest.raises(ValueError, match="text"):
        _fragment(text="   ")
    with pytest.raises(ValueError, match="round_number"):
        _fragment(round_number=0)


def test_a_long_preview_is_cut() -> None:
    assert _fragment(text="a" * 500).preview == "a" * 400 + "…"
    assert _fragment(text="krótki").preview == "krótki"


def test_blank_feedback_is_no_feedback() -> None:
    fragment = _fragment()

    fragment.record_feedback(FragmentVerdict.ON_TRACK, "   ", _AT)

    assert fragment.verdict is FragmentVerdict.ON_TRACK
    assert fragment.feedback is None
    assert not fragment.awaits_feedback


def test_purging_keeps_what_the_promoter_said() -> None:
    fragment = _fragment(file_id=uuid.uuid4())
    fragment.record_feedback(FragmentVerdict.NEEDS_CHANGES, "Dodaj próbę.", _AT)
    length = fragment.char_count

    fragment.purge(_AT)

    assert fragment.is_purged
    assert not fragment.has_file
    assert fragment.char_count == length
    assert fragment.feedback == "Dodaj próbę."
    with pytest.raises(ValueError, match="purged"):
        _ = fragment.content


def test_a_part_stands_where_its_latest_round_left_it() -> None:
    assert part_state(None) is PartState.NOT_SUBMITTED
    waiting = _fragment()
    assert part_state(waiting) is PartState.AWAITING_FEEDBACK
    waiting.record_feedback(FragmentVerdict.NEEDS_ADDITIONS, None, _AT)
    assert part_state(waiting) is PartState.NEEDS_ADDITIONS
