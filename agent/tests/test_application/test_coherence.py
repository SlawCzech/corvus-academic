"""Tests for the coherence check: chapters from the map, digests, and the reduce."""

from typing import Any
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage
from langgraph.types import Send

from src.application import chapters as chapters_module
from src.application.chapters import frame, split_chapters
from src.application.graph import build_action_graph
from src.application.nodes.coherence import (
    check_coherence,
    digest_chapter,
    route_chapters,
)
from src.domain.action import ActionType
from src.domain.analysis import FindingSource
from tests.factories import make_state


def _thesis() -> tuple[str, dict[str, Any]]:
    """A small thesis and the map `app` would compute for it."""
    parts = [
        ("SPIS TREŚCI", "toc", "Wstęp ........ 3\nZakończenie ........ 9\n"),
        (
            "WSTĘP",
            "introduction",
            "Celem pracy jest... H1: płaca jest najważniejsza.\n",
        ),
        ("1.1. Pojęcie motywacji", None, "Motywacja to...\n"),
        ("1.2. Teorie motywacji", None, "Maslow, Herzberg...\n"),
        ("2.1. Metodyka badania", None, "Ankieta, n = 23.\n"),
        ("2.2. Wyniki badania", None, "39% wskazało płacę.\n"),
        ("ZAKOŃCZENIE", "conclusions", "Ok. 70% ceni czynniki pozafinansowe.\n"),
        ("BIBLIOGRAFIA", "bibliography", "1. Maslow (1943).\n"),
    ]
    text, sections = "", []
    for title, canonical, body in parts:
        sections.append(
            {
                "title": title,
                "canonical": canonical,
                "start": len(text),
                "char_count": 0,
            }
        )
        text += f"{title}\n{body}\n"
    return text, {"sections": sections}


# ---------- chapters ----------


def test_numbered_headings_group_into_chapters_between_intro_and_conclusions() -> None:
    text, document_map = _thesis()

    found = split_chapters(text, document_map)

    assert [c.title for c in found] == [
        "1.1. Pojęcie motywacji",
        "2.1. Metodyka badania",
    ]
    assert "Maslow, Herzberg" in found[0].text  # 1.2 belongs to chapter 1
    assert "39% wskazało płacę" in found[1].text
    assert all("ZAKOŃCZENIE" not in c.text for c in found)


def test_no_introduction_in_the_map_means_no_chapters() -> None:
    text, document_map = _thesis()
    sections = [s for s in document_map["sections"] if s["canonical"] != "introduction"]

    assert split_chapters(text, {"sections": sections}) == []
    assert split_chapters(text, {}) == []


def test_a_long_chapter_is_cut_into_parts_not_truncated() -> None:
    text, document_map = _thesis()
    with patch.object(chapters_module, "_CHUNK_CHARS", 20):
        found = split_chapters(text, document_map)

    assert any("(część 1/" in c.title for c in found)
    joined = "".join(c.text for c in found if c.title.startswith("2.1"))
    assert "39% wskazało płacę" in joined.replace("\n", "")


def test_too_many_parts_are_merged_down_to_the_cap() -> None:
    text, document_map = _thesis()
    with (
        patch.object(chapters_module, "_CHUNK_CHARS", 10),
        patch.object(chapters_module, "_MAX_CHUNKS", 3),
    ):
        found = split_chapters(text, document_map)

    assert len(found) == 3


def test_frame_takes_the_last_heading_of_its_kind() -> None:
    """The table of contents names the introduction too; the body's one counts."""
    text, document_map = _thesis()

    assert frame(text, document_map, "introduction").startswith("WSTĘP")
    assert "70%" in frame(text, document_map, "conclusions")
    assert frame(text, document_map, "abstract") == ""


# ---------- nodes ----------


def test_route_sends_one_digest_per_chapter() -> None:
    text, document_map = _thesis()
    state = make_state(context={"text": text, "document_map": document_map})

    routed = route_chapters(state)

    assert all(isinstance(r, Send) for r in routed)
    sends = [r for r in routed if isinstance(r, Send)]
    assert [s.arg["title"] for s in sends] == [
        "1.1. Pojęcie motywacji",
        "2.1. Metodyka badania",
    ]
    assert sends[0].arg["model"] == state["model"]


def test_route_without_chapters_goes_straight_to_the_check() -> None:
    assert route_chapters(make_state(context={"text": "x"})) == ["check_coherence"]


def test_digest_failure_is_reported_not_raised() -> None:
    llm = MagicMock()
    llm.invoke.side_effect = RuntimeError("ollama down")
    with patch("src.application.nodes.coherence.get_llm", return_value=llm):
        update = digest_chapter(
            {"index": 0, "title": "1.1", "text": "x", "model": "m", "language": "pl"}
        )

    assert update == {"node_errors": ["digest 1.1: ollama down"]}


def test_coherence_without_digests_does_nothing() -> None:
    with patch("src.application.nodes.coherence.get_llm") as get_llm:
        assert check_coherence(make_state(context={"text": "x"})) == {}
    get_llm.assert_not_called()


# ---------- the whole map-reduce, through the graph ----------


def test_the_review_digests_every_chapter_and_checks_them_together() -> None:
    text, document_map = _thesis()
    digests_asked: list[str] = []
    coherence_prompts: list[str] = []

    def _answer(messages: list[Any], **_: Any) -> AIMessage:  # noqa: ANN401
        system, user = str(messages[0].content), str(messages[1].content)
        if "record what it says" in system:
            digests_asked.append(user.splitlines()[0])
            number = "39%" if "Wyniki" in user else "brak liczb"
            return AIMessage(
                content='{"summary": "Streszczenie.", "claims": [{"claim": "'
                + number
                + '", "quote": ""}]}'
            )
        if "holds together as an argument" in system:
            coherence_prompts.append(user)
            return AIMessage(
                content='[{"section": "Zakończenie", "description": "Wnioski '
                'przeczą wynikom", "severity": "major", "suggestion": "-", '
                '"quote": "Ok. 70% ceni czynniki pozafinansowe."}]'
            )
        if "formal thesis review" in system:
            return AIMessage(
                content='{"scores": [{"criteria": "S", "points": 5}], '
                '"review_text": "R.", "recommendation": "Zwrócić do poprawy"}'
            )
        return AIMessage(content="[]")

    llm = MagicMock()
    llm.invoke.side_effect = _answer
    state = make_state(
        context={"text": text, "document_map": document_map, "guidelines": "r"}
    )
    for module in ("structure", "methodology", "requirements", "review", "coherence"):
        patch(f"src.application.nodes.{module}.get_llm", return_value=llm).start()
    try:
        final = build_action_graph(ActionType.GENERATE_REVIEW).invoke(state)
    finally:
        patch.stopall()

    assert sorted(digests_asked) == [
        "## 1.1. Pojęcie motywacji",
        "## 2.1. Metodyka badania",
    ]
    # The reduce sees every digest, in chapter order, next to both frames.
    prompt = coherence_prompts[0]
    assert prompt.index("1.1. Pojęcie") < prompt.index("2.1. Metodyka")
    assert "H1: płaca" in prompt and "70%" in prompt and "39%" in prompt
    coherence = [f for f in final["findings"] if f.source == FindingSource.COHERENCE]
    assert [f.description for f in coherence] == ["Wnioski przeczą wynikom"]
