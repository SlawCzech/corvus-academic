"""Tests for the review_fragment node."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage

from src.application.graph import build_action_graph
from src.application.nodes.review_fragment import _context_lines, review_fragment
from src.application.prompts.review_fragment import get_system_prompt
from src.application.state import ActionState
from src.domain.action import ActionType
from src.infrastructure.llm_factory import ModelCredentials, use_credentials
from tests.factories import make_state

_TEXT = (
    "Rozdział omawia teorię kapitału ludzkiego Beckera. "
    "Autor stawia tezę, że wykształcenie nie gwarantuje zatrudnienia w regionie."
)
_QUOTE = "wykształcenie nie gwarantuje zatrudnienia"


def _reply(**fields: Any) -> str:  # noqa: ANN401
    reply: dict[str, Any] = {
        "summary": "Fragment omawia teorię kapitału ludzkiego.\n\nAutor stawia tezę.",
        "answer": "",
        "direction": "on_track",
        "strengths": ["Jasno postawiona teza."],
        "changes": [],
        "additions": [],
        "addressed": [],
        "next_step": "Przejść do danych regionalnych.",
    }
    return json.dumps(reply | fields)


def _state(**context: Any) -> ActionState:  # noqa: ANN401
    return make_state(
        action_type=ActionType.REVIEW_FRAGMENT,
        context={
            "text": _TEXT,
            "part_name": "Rozdział 1",
            "round_number": 1,
            "current_topic": "Bezrobocie osób wykształconych",
        }
        | context,
    )


def _run(response: str, state: ActionState | None = None) -> tuple[ActionState, str]:
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=response)
    with patch("src.application.nodes.review_fragment.get_llm", return_value=mock_llm):
        result = review_fragment(state or _state())
    sent = (
        str(mock_llm.invoke.call_args.args[0][1].content)
        if mock_llm.invoke.called
        else ""
    )
    return result, sent


def test_a_fragment_on_track() -> None:
    result, _ = _run(_reply())

    output = result["output"]
    assert output is not None
    assert "teorię kapitału" in output["summary"]
    assert output["direction"] == "on_track"
    assert output["strengths"] == ["Jasno postawiona teza."]
    assert result["error"] is None


def test_a_change_with_an_invented_quote_is_dropped() -> None:
    changes = [
        {"point": "Doprecyzować tezę.", "quote": _QUOTE},
        {
            "point": "Poprawić akapit.",
            "quote": "ten cytat nie występuje nigdzie w całym tekście pracy",
        },
    ]

    result, _ = _run(_reply(direction="needs_changes", changes=changes))

    output = result["output"]
    assert output is not None
    assert [c["point"] for c in output["changes"]] == ["Doprecyzować tezę."]
    assert output["direction"] == "needs_changes"


def test_the_list_is_capped_after_grounding() -> None:
    """A dropped item must not cost a real one its place."""
    invented = {
        "point": "Zmyślone.",
        "quote": "tego cytatu nie ma nigdzie w całym tekście tej pracy",
    }
    real = [{"point": f"Punkt {n}.", "quote": _QUOTE} for n in range(5)]
    additions = [f"Dodatek {n}." for n in range(5)]

    result, _ = _run(_reply(changes=[invented, *real], additions=additions))

    output = result["output"]
    assert output is not None
    assert [c["point"] for c in output["changes"]] == [
        "Punkt 0.",
        "Punkt 1.",
        "Punkt 2.",
    ]
    assert len(output["additions"]) == 3


def test_needing_work_names_the_work() -> None:
    """Grounding may leave nothing to change; then the fragment is on track."""
    invented = {
        "point": "Zmyślone.",
        "quote": "tego cytatu nie ma nigdzie w całym tekście tej pracy",
    }

    changes, _ = _run(_reply(direction="needs_changes", changes=[invented]))
    additions, _ = _run(_reply(direction="needs_additions"))

    assert changes["output"] is not None
    assert changes["output"]["direction"] == "on_track"
    assert additions["output"] is not None
    assert additions["output"]["direction"] == "on_track"


def test_the_direction_is_read_loosely_and_required() -> None:
    upper, _ = _run(_reply(direction="ON_TRACK"))
    unknown, _ = _run(_reply(direction="excellent"))

    assert upper["output"] is not None
    assert upper["output"]["direction"] == "on_track"
    assert unknown["error"] is not None


def test_a_summary_is_required() -> None:
    result, _ = _run(_reply(summary=""))

    assert result["error"] is not None


def test_nothing_to_read_never_reaches_the_model() -> None:
    result, sent = _run(_reply(), _state(text="   "))

    assert result["error"] is not None
    assert sent == ""


def test_a_failing_model_is_recorded_not_raised() -> None:
    mock_llm: Any = MagicMock()
    mock_llm.invoke.side_effect = Exception("API timeout")

    with patch("src.application.nodes.review_fragment.get_llm", return_value=mock_llm):
        result = review_fragment(_state())

    assert result["error"] is not None
    assert result["output"] is None


def test_the_context_reaches_the_prompt() -> None:
    state = _state(
        detail="Czy Becker wystarczy?",
        field_of_study="Ekonomia",
        recent_notes=["Ustalono zakres rozdziału."],
        other_parts=[{"name": "Wstęp", "state": "on_track"}],
    )

    _, sent = _run(_reply(), state)

    assert "Rozdział 1" in sent
    assert "Bezrobocie osób wykształconych" in sent
    assert "Czy Becker wystarczy?" in sent
    assert "Ustalono zakres rozdziału." in sent
    assert "Wstęp (on_track)" in sent
    assert "teorię kapitału ludzkiego Beckera" in sent


def test_a_later_round_sees_the_previous_feedback_and_text() -> None:
    state = _state(
        round_number=2,
        previous_verdict="needs_changes",
        previous_feedback="Uzasadnij dobór próby.",
        previous_text="POPRZEDNIA RUNDA",
    )

    _, sent = _run(_reply(addressed=["Dobór próby."]), state)

    assert "Round: 2" in sent
    assert "needs_changes" in sent
    assert "Uzasadnij dobór próby." in sent
    assert "POPRZEDNIA RUNDA" in sent


def test_the_local_model_says_where_the_text_was_cut() -> None:
    long_text = _TEXT + " " + "a" * 20000 + " KONIEC FRAGMENTU"

    _, sent = _run(_reply(), _state(text=long_text))

    assert "KONIEC FRAGMENTU" not in sent
    assert "you have not seen the rest" in sent


def test_a_later_round_shares_the_budget_between_the_two_texts() -> None:
    state = _state(previous_text="b" * 8000, text=_TEXT + " " + "a" * 8000)

    _, sent = _run(_reply(), state)

    assert sent.count("b") < 6500
    assert sent.count("you have not seen the rest") == 2


def test_a_hosted_model_reads_it_whole() -> None:
    long_text = _TEXT + " " + "a" * 20000 + " KONIEC FRAGMENTU"
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=_reply())

    with (
        patch("src.application.nodes.review_fragment.get_llm", return_value=mock_llm),
        use_credentials(ModelCredentials(provider="claude", api_key="k")),
    ):
        review_fragment(_state(text=long_text))

    assert "KONIEC FRAGMENTU" in str(mock_llm.invoke.call_args.args[0][1].content)


def test_the_prompt_keeps_it_formative() -> None:
    prompt = get_system_prompt("pl")

    assert "work in progress" in prompt
    assert "Never report as missing" in prompt
    assert "Polish" in prompt
    assert "English" in get_system_prompt("en")


def test_the_graph_is_one_node() -> None:
    graph = build_action_graph(ActionType.REVIEW_FRAGMENT)

    assert "review_fragment" in graph.get_graph().nodes


def test_a_master_thesis_is_not_read_as_a_first_piece_of_research() -> None:
    message = _context_lines({"thesis_type": "master_article"})

    assert any("master's thesis" in line for line in message)


def test_the_aim_reaches_the_fragment_as_orientation() -> None:
    message = "\n".join(_context_lines({"research_aim": "Hipoteza: X."}))

    assert "Hipoteza: X." in message
    assert "not expected to carry out the whole aim" in message
