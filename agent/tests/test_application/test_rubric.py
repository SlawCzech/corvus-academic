from src.application.rubric import (
    METHODOLOGY_SECTIONS,
    REQUIREMENTS_SECTIONS,
    REVIEW_SECTIONS,
    render_guidelines,
)

_SECTIONS = {
    "elements": "Wstęp z celem.",
    "formal": "Objętość sugerowana.",
    "merit": "Logiczny tok wywodu.",
    "severity": "CRITICAL: brak wstępu.",
}


def test_the_requirements_check_reads_the_rules_and_their_weight() -> None:
    text = render_guidelines({"guidelines": _SECTIONS}, REQUIREMENTS_SECTIONS)

    assert "Wstęp z celem." in text
    assert "Objętość sugerowana." in text
    assert "CRITICAL: brak wstępu." in text
    assert "Logiczny tok wywodu." not in text


def test_methodology_and_review_never_see_the_severity_rules() -> None:
    for sections in (METHODOLOGY_SECTIONS, REVIEW_SECTIONS):
        text = render_guidelines({"guidelines": _SECTIONS}, sections)

        assert "Logiczny tok wywodu." in text
        assert "CRITICAL" not in text
        assert "Objętość" not in text


def test_a_rubric_without_sections_goes_whole() -> None:
    whole = "## 5. CRITICAL: brak celu pracy."

    assert render_guidelines({"guidelines": whole}, REVIEW_SECTIONS) == whole


def test_no_rubric_is_an_empty_block() -> None:
    assert render_guidelines({}, REQUIREMENTS_SECTIONS) == ""
