"""Tests for checking findings against the thesis and against each other."""

from typing import Any
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage

from src.application.graph import build_action_graph
from src.application.grounding import (
    ThesisText,
    normalize,
    same_problem,
    verify_findings,
)
from src.application.nodes.verify import verify
from src.domain.action import ActionType
from src.domain.analysis import Finding, FindingSeverity, FindingSource
from tests.factories import make_state

_THESIS = (
    "WSTĘP\n\nCelem pracy jest przedstawienie wpływu kryptowalut na system "
    "finansowy w Polsce.\n\n3.1. Opis badania\n\nW celu poznania opinii na "
    "temat kryptowalut przeprowadzono ankietę wśród znajomych autora. Ankieta "
    "została udostępniona w mediach społecznościowych."
)


def _f(
    description: str,
    quote: str = "",
    source: FindingSource = FindingSource.STRUCTURE,
    severity: FindingSeverity = FindingSeverity.MAJOR,
) -> Finding:
    return Finding(
        section="Wstęp",
        description=description,
        severity=severity,
        suggestion="-",
        source=source,
        quote=quote,
    )


# ---------- quotes ----------


def test_normalize_drops_punctuation_case_and_layout() -> None:
    assert normalize("„Celem  pracy”\njest — przedstawienie!") == (
        "celem pracy jest przedstawienie"
    )


def test_a_verbatim_quote_is_found_across_line_breaks_and_quote_marks() -> None:
    text = ThesisText(_THESIS)

    assert text.contains("„Celem pracy jest przedstawienie wpływu kryptowalut”")
    assert text.contains("przeprowadzono ankietę wśród znajomych autora.")


def test_an_ellipsis_joins_pieces_that_are_each_verbatim() -> None:
    text = ThesisText(_THESIS)

    assert text.contains("Celem pracy jest … system finansowy w Polsce")
    assert text.contains("przeprowadzono ankietę [...] w mediach społecznościowych")


def test_a_near_verbatim_quote_passes() -> None:
    # One word inflected differently: a copying slip, not an invention.
    text = ThesisText(_THESIS)

    assert text.contains(
        "W celu poznania opinii na temat kryptowaluty przeprowadzono ankietę "
        "wśród znajomych autora"
    )


def test_an_invented_quote_fails() -> None:
    text = ThesisText(_THESIS)

    assert not text.contains("Hipoteza badawcza zakłada, że banki upadną do 2030")
    assert not text.contains("Celem pracy jest … badanie wszystkich Polaków w 2024")


def test_an_empty_or_tiny_quote_claims_nothing() -> None:
    text = ThesisText(_THESIS)

    assert text.contains("")
    assert text.contains("Rozdział 7")  # too short to call an invention


# ---------- duplicates ----------


def test_findings_on_the_same_passage_from_two_analyses_are_one_problem() -> None:
    a = _f("Ankieta bez opisu próby", "przeprowadzono ankietę wśród znajomych")
    b = _f(
        "Próba nie jest opisana",
        "przeprowadzono ankietę wśród znajomych autora",
        source=FindingSource.METHODOLOGY,
    )

    assert same_problem(a, b)


def test_findings_saying_the_same_thing_are_one_problem() -> None:
    a = _f("Brak hipotez badawczych we wstępie pracy")
    b = _f("We wstępie brak hipotezy badawczej", source=FindingSource.REQUIREMENTS)

    assert same_problem(a, b)


def test_different_problems_stay_apart() -> None:
    a = _f("Brak hipotez badawczych we wstępie")
    b = _f(
        "Bibliografia zawiera za mało źródeł obcojęzycznych",
        source=FindingSource.REQUIREMENTS,
    )

    assert not same_problem(a, b)


def test_one_analysis_is_never_merged_with_itself() -> None:
    a = _f("Brak hipotez badawczych we wstępie")

    assert not same_problem(a, _f("Brak hipotez badawczych we wstępie"))


# ---------- verify_findings ----------


def test_verify_drops_ungrounded_and_keeps_absences() -> None:
    real = _f("Ankieta bez opisu", "przeprowadzono ankietę wśród znajomych autora")
    absent = _f("Brak hipotez")  # an absence has nothing to quote
    invented = _f("Zła hipoteza", "Hipoteza H1 zakłada spadek kursu do zera w 2030")

    result = verify_findings([real, absent, invented], _THESIS)

    assert result.kept == [real, absent]
    assert result.ungrounded == [invented]


def test_verify_merges_into_the_more_severe_finding_in_the_first_place() -> None:
    minor = _f("Brak hipotez badawczych we wstępie", severity=FindingSeverity.MINOR)
    other = _f("Brak opisu struktury", source=FindingSource.METHODOLOGY)
    critical = _f(
        "We wstępie brak hipotezy badawczej",
        source=FindingSource.REQUIREMENTS,
        severity=FindingSeverity.CRITICAL,
    )

    result = verify_findings([minor, other, critical], _THESIS)

    assert result.kept == [critical, other]
    assert result.merged == [minor]
    summary = result.summary()
    assert summary["kept"] == 2
    assert summary["merged"] == 1


# ---------- the node ----------


def test_verify_node_replaces_the_findings_instead_of_adding_to_them() -> None:
    invented = _f("x", "zdanie którego w pracy na pewno nie ma nigdzie")
    kept = _f("Brak hipotez")
    state = make_state(context={"text": _THESIS}, findings=[kept, invented])

    update: dict[str, Any] = dict(verify(state))

    assert update["findings"].value == [kept]
    assert len(update["verification"]["ungrounded"]) == 1


def test_verify_node_passes_findings_through_when_the_check_breaks() -> None:
    state = make_state(context={"text": _THESIS}, findings=[_f("x")])

    with patch(
        "src.application.nodes.verify.verify_findings",
        side_effect=RuntimeError("boom"),
    ):
        update: dict[str, Any] = dict(verify(state))

    assert update == {"node_errors": ["verify: boom"]}


def test_the_review_reads_only_verified_findings() -> None:
    """End to end through the graph: an invented quote never reaches the review."""
    real = (
        '[{"section": "3.1", "description": "Ankieta bez opisu próby", '
        '"severity": "major", "suggestion": "-", '
        '"quote": "przeprowadzono ankietę wśród znajomych autora"}]'
    )
    invented = (
        '[{"section": "Wstęp", "description": "Hipoteza jest błędna", '
        '"severity": "critical", "suggestion": "-", '
        '"quote": "Hipoteza H1 zakłada upadek wszystkich banków"}]'
    )
    review = (
        '{"scores": [{"criteria": "Struktura", "points": 5}], '
        '"review_text": "Recenzja.", "recommendation": "Zwrócić do poprawy"}'
    )
    seen: list[str] = []

    def _answer(messages: list[Any], **_: Any) -> AIMessage:  # noqa: ANN401
        system = str(messages[0].content)
        if "formal thesis review" in system:
            seen.append(str(messages[1].content))
            return AIMessage(content=review)
        if "YOUR SCOPE" in system and "structure" in system.split("YOUR SCOPE")[0]:
            return AIMessage(content=real)
        return AIMessage(content=invented if "methodology" in system else "[]")

    llm = MagicMock()
    llm.invoke.side_effect = _answer
    state = make_state(context={"text": _THESIS, "guidelines": "rules"})

    for module in ("structure", "methodology", "requirements", "review"):
        patch(f"src.application.nodes.{module}.get_llm", return_value=llm).start()
    try:
        final = build_action_graph(ActionType.GENERATE_REVIEW).invoke(state)
    finally:
        patch.stopall()

    assert "Hipoteza jest błędna" not in seen[0]
    assert all(f.description != "Hipoteza jest błędna" for f in final["findings"])
    assert final["verification"]["ungrounded"][0]["description"] == (
        "Hipoteza jest błędna"
    )
