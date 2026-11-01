"""Tests for the block that tells a node what the thesis is meant to do."""

from typing import Any

from src.application.brief import render_brief, render_research
from src.application.nodes.coherence import check_coherence
from src.application.nodes.methodology import analyze_methodology


def test_without_area_or_aim_there_is_no_new_instruction() -> None:
    brief = render_brief({"current_topic": "Bazary", "field_of_study": "Zarządzanie"})

    assert "Thesis topic: Bazary" in brief
    assert "Field of study: Zarządzanie" in brief
    assert "add no requirements" not in brief
    assert render_research({"research_area": None, "research_aim": ""}) == ""


def test_area_and_aim_come_with_the_rule_for_reading_them() -> None:
    brief = render_brief(
        {"research_area": "ekonomia instytucjonalna", "research_aim": "Cel: X"},
        reading="Czytaj tak.",
    )

    assert "Research area: ekonomia instytucjonalna" in brief
    assert "Agreed aim and hypotheses:\nCel: X" in brief
    assert "add no requirements" in brief
    assert brief.rstrip().endswith("Czytaj tak.")


def test_the_review_context_is_read_from_its_metadata() -> None:
    brief = render_brief(
        {"metadata": {"title": "Bazary", "field_of_study": "Ekonomia"}}
    )

    assert "Thesis topic: Bazary" in brief
    assert "Field of study: Ekonomia" in brief


def test_an_unsettled_topic_is_said_out_loud() -> None:
    assert "Thesis topic: not settled yet" in render_brief({})


class _Capture:
    """Stands in for `invoke_structured`, remembering what the model was sent."""

    def __init__(self) -> None:
        self.sent = ""

    def __call__(self, _llm: Any, messages: list[Any], *_: Any, **__: Any) -> list[Any]:  # noqa: ANN401
        self.sent = str(messages[-1].content)
        return []


def test_methodology_is_told_what_the_thesis_is_for(monkeypatch: Any) -> None:  # noqa: ANN401
    capture = _Capture()
    module = "src.application.nodes.methodology"
    monkeypatch.setattr(f"{module}.invoke_structured", capture)
    monkeypatch.setattr(f"{module}.get_llm", lambda _model: object())
    state: Any = {
        "model": "m",
        "context": {
            "text": "Tekst pracy.",
            "current_topic": "Bazary",
            "research_aim": "Cel: X",
        },
    }

    analyze_methodology(state)

    assert "Thesis topic: Bazary" in capture.sent
    assert "Agreed aim and hypotheses:\nCel: X" in capture.sent


def test_only_coherence_is_asked_to_compare_the_aims(monkeypatch: Any) -> None:  # noqa: ANN401
    capture = _Capture()
    module = "src.application.nodes.coherence"
    monkeypatch.setattr(f"{module}.invoke_structured", capture)
    monkeypatch.setattr(f"{module}.get_llm", lambda _model: object())
    digest = {"index": 0, "title": "R1", "summary": "S", "claims": []}
    state: Any = {
        "model": "m",
        "chapter_digests": [digest],
        "context": {"text": "Tekst.", "research_aim": "Cel: X"},
    }

    check_coherence(state)

    assert "major at most" in capture.sent
