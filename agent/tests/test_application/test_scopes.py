"""Tests for the division of scope between the review's three analyses."""

import pytest

from src.application.nodes.requirements import (
    _get_system_prompt,  # pyright: ignore[reportPrivateUsage]
)
from src.application.prompts import methodology, structure
from src.application.prompts.scopes import SCOPES, scope_instruction
from src.domain.analysis import FindingSource

_PROMPTS = {
    FindingSource.STRUCTURE: structure.get_system_prompt,
    FindingSource.METHODOLOGY: methodology.get_system_prompt,
    FindingSource.REQUIREMENTS: _get_system_prompt,
}


def test_every_analysis_has_a_scope() -> None:
    """A source without a scope would be told nothing about its boundaries."""
    assert set(SCOPES) == set(FindingSource)


@pytest.mark.parametrize("own", list(FindingSource))
def test_the_instruction_names_its_own_scope_and_both_others(
    own: FindingSource,
) -> None:
    text = scope_instruction(own)

    assert f"YOUR SCOPE — report only problems of this kind: {SCOPES[own]}" in text
    for other in FindingSource:
        if other is not own:
            assert f"- {other.value}: {SCOPES[other]}" in text
    assert f"- {own.value}:" not in text


@pytest.mark.parametrize("own", list(FindingSource))
@pytest.mark.parametrize("language", ["pl", "en"])
def test_each_analysis_prompt_carries_its_scope(
    own: FindingSource, language: str
) -> None:
    assert scope_instruction(own) in _PROMPTS[own](language)
