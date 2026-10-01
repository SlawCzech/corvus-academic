"""Tests for the bibliography check: matching rules, Crossref, and the agent loop."""

import json
import logging
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from src.application.bibliography import (
    MISMATCH,
    UNRESOLVED,
    VERIFIED,
    bibliography_section,
    doi_in,
    first_surname,
    is_website,
    match,
    search_title,
)
from src.application.graph import build_action_graph
from src.application.nodes import bibliography as nodes
from src.domain.action import ActionType
from src.infrastructure.checkpoints import serializer
from src.infrastructure.crossref import (
    CrossrefClient,
    CrossrefUnavailableError,
    Pace,
    Work,
)
from tests.factories import make_state

_LAIBSON = Work(
    doi="10.1162/003355397555253",
    title="Golden Eggs and Hyperbolic Discounting",
    year=1997,
    authors=("Laibson",),
    venue="The Quarterly Journal of Economics",
    kind="journal-article",
    score=87.6,
)
_LAIBSON_ENTRY = (
    "Laibson, D. (1997). Golden eggs and hyperbolic discounting. "
    "Quarterly Journal of Economics, 112(2), 443–477."
)
_FAKE_ENTRY = (
    "Nowak, T. (2019). The cryptographic foundations of monetary sovereignty. "
    "Journal of Monetary Economics, 104, 12–39."
)
_WEB_ENTRY = (
    "Bankier.pl (2023). Czy kryptowaluty zagrażają bankom? https://www.bankier.pl"
)


# ---------- matching rules ----------


def test_a_record_with_the_same_title_year_and_author_verifies() -> None:
    assert match(_LAIBSON_ENTRY, 1997, [_LAIBSON]).status == VERIFIED


def test_the_right_work_with_the_wrong_year_is_a_mismatch() -> None:
    check = match(_LAIBSON_ENTRY.replace("1997", "2001"), 2001, [_LAIBSON])

    assert check.status == MISMATCH
    assert "rok 1997 zamiast 2001" in check.note
    assert check.doi == _LAIBSON.doi


def _record(title: str, author: str, year: int | None, kind: str) -> Work:
    return Work(
        doi=f"10.1/{author.lower()}{year}",
        title=title,
        year=year,
        authors=(author,),
        venue="",
        kind=kind,
        score=50.0,
    )


_NORTH_ENTRY = (
    "North, D. C., i Thomas, R. P. (1973). The rise of the Western world: "
    "A new economic history. Cambridge University Press."
)
_RISE = "The Rise of the Western World"


def test_a_books_reviews_do_not_make_it_a_mismatch() -> None:
    """What Crossref returns for a classic: its reviews first, the book fourth."""
    works = [
        _record(
            f"{_RISE}: A New Economic History", "Shneidman", 1973, "journal-article"
        ),
        _record(
            f"{_RISE}: A New Economic History", "Knauerhase", 1974, "journal-article"
        ),
        _record(_RISE, "North", 1973, "monograph"),
    ]

    check = match(_NORTH_ENTRY, 1973, works)

    assert (check.status, check.doi) == (VERIFIED, "10.1/north1973")


def test_only_reviews_leave_the_book_to_the_agent() -> None:
    reviews = [_record(_RISE, "Shneidman", 1973, "journal-article")]

    assert match(_NORTH_ENTRY, 1973, reviews).status == UNRESOLVED


def test_a_later_edition_of_a_book_is_the_book() -> None:
    entry = "Wallerstein, I. (1974). The modern world-system I. Academic Press."
    edition = _record("The Modern World-System I", "Wallerstein", 2011, "monograph")

    check = match(entry, 1974, [edition])

    assert check.status == VERIFIED
    assert "2011" in check.note


def test_an_article_known_only_from_reprints_is_not_a_wrong_year() -> None:
    entry = (
        "Alchian, A. A., i Demsetz, H. (1972). Production, information costs, "
        "and economic organization. American Economic Review, 62(5), 777–795."
    )
    title = "Production, Information Costs, and Economic Organization"
    reprints = [
        _record(title, "Alchian", 2009, "book-chapter"),
        _record(title, "Alchian", 1975, "journal-article"),
    ]

    assert match(entry, 1972, reprints).status == VERIFIED


def test_a_book_found_in_a_catalogue_says_which() -> None:
    entry = "Wyczański, A. (1960). Studia nad folwarkiem szlacheckim w Polsce. PWN."
    # Spelled the way a foreign catalogue might: no diacritics.
    record = _record(
        "Studia nad folwarkiem szlacheckim w Polsce", "Wyczanski", 1960, "book"
    )

    check = match(entry, 1960, [record], "Biblioteka Narodowa")

    assert check.status == VERIFIED
    assert check.note == "Katalog: Biblioteka Narodowa."


def test_a_reference_is_searched_by_surname_and_main_title() -> None:
    assert first_surname("North, D. C., i Thomas, R. P.") == "North"
    assert first_surname("Hagen, W. W.") == "Hagen"
    assert search_title("Ordinary Prussians: Brandenburg Junkers and villagers") == (
        "Ordinary Prussians"
    )
    assert search_title("Gospodarka polska a europejska w XVI–XVIII wieku") == (
        "Gospodarka polska a europejska w XVI-XVIII wieku"
    )


def test_an_unrelated_record_leaves_the_entry_open() -> None:
    assert match(_FAKE_ENTRY, 2019, [_LAIBSON]).status == UNRESOLVED
    assert match(_FAKE_ENTRY, 2019, []).status == UNRESOLVED


def test_websites_and_dois_are_recognised() -> None:
    assert is_website(_WEB_ENTRY)
    assert not is_website("Smith (2020). Title. https://doi.org/10.1000/xyz123")
    assert doi_in("Smith (2020). Title. https://doi.org/10.1000/xyz123.") == (
        "10.1000/xyz123"
    )


def test_the_bibliography_is_cut_from_its_last_heading() -> None:
    text = "SPIS\nBibliografia .... 9\nWSTĘP\ntekst\nBIBLIOGRAFIA\n1. A (2020).\n"
    document_map = {
        "sections": [
            {"canonical": "bibliography", "start": text.index("Bibliografia")},
            {"canonical": "introduction", "start": text.index("WSTĘP")},
            {"canonical": "bibliography", "start": text.index("BIBLIOGRAFIA")},
        ]
    }

    assert bibliography_section(text, document_map) == "BIBLIOGRAFIA\n1. A (2020)."
    assert bibliography_section(text, {}) == ""


# ---------- Crossref client ----------


def _client(handler: Any) -> CrossrefClient:  # noqa: ANN401
    return CrossrefClient(
        httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url="https://api.crossref.org",
        ),
        # Retries are waited out for real otherwise; nothing here needs the wait.
        Pace(sleep=lambda _: None),
    )


def test_search_sends_the_reference_and_parses_records() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        item = {
            "DOI": _LAIBSON.doi,
            "title": [_LAIBSON.title],
            "issued": {"date-parts": [[1997, 5, 1]]},
            "author": [{"family": "Laibson", "given": "D."}],
            "container-title": [_LAIBSON.venue],
            "type": "journal-article",
            "score": 87.6,
        }
        return httpx.Response(200, json={"message": {"items": [item]}})

    works = _client(handler).search(_LAIBSON_ENTRY)

    assert works == [_LAIBSON]
    assert seen[0].url.params["query.bibliographic"] == _LAIBSON_ENTRY


def test_lookup_of_an_unknown_doi_is_none_and_an_outage_raises() -> None:
    assert _client(lambda r: httpx.Response(404)).lookup("10.1/nope") is None
    with pytest.raises(CrossrefUnavailableError):
        _client(lambda r: httpx.Response(503)).lookup("10.1/x")


# ---------- the whole action ----------


def _references_reply() -> str:
    return json.dumps(
        {
            "references": [
                {"entry": _LAIBSON_ENTRY, "year": 1997},
                {"entry": _WEB_ENTRY, "year": 2023},
                {"entry": _FAKE_ENTRY, "year": 2019},
            ]
        }
    )


def _state() -> Any:  # noqa: ANN401
    entries = [_LAIBSON_ENTRY, _WEB_ENTRY, _FAKE_ENTRY]
    listing = "".join(f"{i}. {e}\n" for i, e in enumerate(entries, start=1))
    text = f"WSTĘP\n...\nBIBLIOGRAFIA\n{listing}"
    document_map = {
        "sections": [
            {"canonical": "introduction", "start": 0},
            {"canonical": "bibliography", "start": text.index("BIBLIOGRAFIA")},
        ]
    }
    return make_state(
        action_type=ActionType.VERIFY_BIBLIOGRAPHY,
        context={"text": text, "document_map": document_map},
    )


def _llm(agent_turns: list[AIMessage], seen: list[list[Any]]) -> MagicMock:
    turns = iter(agent_turns)

    def _answer(messages: list[Any], **_: Any) -> AIMessage:  # noqa: ANN401
        system = str(messages[0].content)
        if "List every entry" in system:
            return AIMessage(content=_references_reply())
        if "Give a verdict for each reference" in system:
            seen.append(messages)
            return AIMessage(
                content='{"verdicts": [{"index": 2, "status": "suspicious", '
                '"note": "Brak takiego artykułu w JME."}]}'
            )
        seen.append(messages)
        return next(turns)

    llm = MagicMock()
    llm.invoke.side_effect = _answer
    llm.bind_tools.return_value = llm
    return llm


def _crossref() -> MagicMock:
    client = MagicMock()
    client.search.side_effect = lambda q, rows=3: [_LAIBSON] if "Laibson" in q else []
    return client


def test_only_what_matching_left_open_reaches_the_agent() -> None:
    seen: list[list[Any]] = []
    agent_turns = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "search_crossref",
                    "args": {"query": "cryptographic foundations of monetary"},
                    "id": "call-1",
                }
            ],
        ),
        AIMessage(content="Done."),
    ]
    llm = _llm(agent_turns, seen)

    with (
        patch("src.application.nodes.bibliography.get_llm", return_value=llm),
        patch(
            "src.application.nodes.bibliography.CrossrefClient",
            return_value=_crossref(),
        ),
    ):
        final = build_action_graph(ActionType.VERIFY_BIBLIOGRAPHY).invoke(_state())

    # The agent was shown the one open entry, by its index, and nothing else.
    listing = str(seen[0][1].content)
    assert "[2] Nowak" in listing
    assert "Laibson" not in listing and "bankier" not in listing
    # Its tool ran, and the result came back into the conversation.
    assert "RESULT no records" in str(seen[-1][1].content)

    rows = final["output"]["references"]
    assert [r["status"] for r in rows] == ["verified", "website", "suspicious"]
    assert rows[0]["doi"] == _LAIBSON.doi
    assert final["output"]["suspicious"] == 1
    assert final["status"] == "bibliography_checked"


def test_a_book_crossref_does_not_have_is_settled_by_a_catalogue() -> None:
    """No model, no agent: the National Library knows the book."""
    entry = "Topolski, J. (1977). Gospodarka polska a europejska w XVI–XVIII wieku. WP."
    listed = json.dumps(
        {
            "references": [
                {
                    "entry": entry,
                    "authors": "Topolski, J.",
                    "year": 1977,
                    "title": "Gospodarka polska a europejska w XVI–XVIII wieku",
                }
            ]
        }
    )
    llm = _llm([], [])
    llm.invoke.side_effect = lambda messages, **_: AIMessage(content=listed)
    crossref = MagicMock()
    crossref.search.return_value = []
    library = MagicMock()
    library.name = "Biblioteka Narodowa"
    library.search.return_value = [
        _record(
            "Gospodarka polska a europejska w XVI-XVIII wieku",
            "Topolski",
            1977,
            "książka",
        )
    ]

    with (
        patch("src.application.nodes.bibliography.get_llm", return_value=llm),
        patch(
            "src.application.nodes.bibliography.CrossrefClient", return_value=crossref
        ),
        patch(
            "src.application.nodes.bibliography.NationalLibraryClient",
            return_value=library,
        ),
        patch("src.application.nodes.bibliography.OpenLibraryClient") as open_library,
    ):
        final = build_action_graph(ActionType.VERIFY_BIBLIOGRAPHY).invoke(_state())

    library.search.assert_called_once_with(
        "Gospodarka polska a europejska w XVI-XVIII wieku", "Topolski"
    )
    # Found in the first catalogue: the second is not asked, nor is the agent.
    open_library.return_value.search.assert_not_called()
    llm.bind_tools.assert_not_called()
    row = final["output"]["references"][0]
    assert (row["status"], row["note"]) == ("verified", "Katalog: Biblioteka Narodowa.")


def test_a_bibliography_matching_settles_skips_the_agent() -> None:
    seen: list[list[Any]] = []
    llm = _llm([], seen)
    crossref = MagicMock()
    crossref.search.return_value = [_LAIBSON]
    one = json.dumps({"references": [{"entry": _LAIBSON_ENTRY, "year": 1997}]})
    llm.invoke.side_effect = lambda messages, **_: AIMessage(content=one)

    with (
        patch("src.application.nodes.bibliography.get_llm", return_value=llm),
        patch(
            "src.application.nodes.bibliography.CrossrefClient", return_value=crossref
        ),
    ):
        final = build_action_graph(ActionType.VERIFY_BIBLIOGRAPHY).invoke(_state())

    llm.bind_tools.assert_not_called()
    assert final["output"]["counts"] == {"verified": 1}


def test_the_loop_ends_when_the_budget_is_spent_whatever_the_agent_asks() -> None:
    seen: list[list[Any]] = []
    calls = [
        AIMessage(
            content="",
            tool_calls=[
                {"name": "search_crossref", "args": {"query": f"q{i}"}, "id": f"c{i}"}
            ],
        )
        # One more than the budget: the last call is asked for and not run.
        for i in range(nodes.TOOL_BUDGET + 1)
    ]
    llm = _llm(calls, seen)

    with (
        patch("src.application.nodes.bibliography.get_llm", return_value=llm),
        patch(
            "src.application.nodes.bibliography.CrossrefClient",
            return_value=_crossref(),
        ),
    ):
        crossref = _crossref()
        with patch(
            "src.application.nodes.bibliography.CrossrefClient", return_value=crossref
        ):
            final = build_action_graph(ActionType.VERIFY_BIBLIOGRAPHY).invoke(
                _state(), {"recursion_limit": 100}
            )

    # The tools stay bound on every turn, the last included: the conversation
    # a model is shown again must be the one it wrote in, tools and all.
    assert llm.bind_tools.call_count == nodes.TOOL_BUDGET + 1
    last_turn = seen[-2]
    assert "used up" in str(last_turn[-1].content)
    # One search to match the entries, then the budget — and not one more.
    agent_searches = [
        c for c in crossref.search.call_args_list if str(c.args[0]).startswith("q")
    ]
    assert len(agent_searches) == nodes.TOOL_BUDGET
    assert final["status"] == "bibliography_checked"


def test_no_bibliography_is_an_error() -> None:
    state = make_state(
        action_type=ActionType.VERIFY_BIBLIOGRAPHY, context={"text": "WSTĘP\n"}
    )

    final = build_action_graph(ActionType.VERIFY_BIBLIOGRAPHY).invoke(state)

    assert final["error"] == "no bibliography found in the thesis"
    assert final["output"] is None


def test_the_agents_conversation_checkpoints_without_unregistered_types(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A resumed check must load the agent's messages back — and nothing else."""
    seen: list[list[Any]] = []
    llm = _llm([AIMessage(content="Done.")], seen)
    saver = InMemorySaver(serde=serializer())
    config = {"configurable": {"thread_id": "bib"}}

    with (
        patch("src.application.nodes.bibliography.get_llm", return_value=llm),
        patch(
            "src.application.nodes.bibliography.CrossrefClient",
            return_value=_crossref(),
        ),
        caplog.at_level(logging.WARNING),
    ):
        graph = build_action_graph(ActionType.VERIFY_BIBLIOGRAPHY, checkpointer=saver)
        graph.invoke(_state(), config)
        messages = graph.get_state(config).values["messages"]

    assert any(isinstance(m, AIMessage) for m in messages)
    assert "unregistered type" not in caplog.text
