"""Resuming a run from its checkpoints: a retry redoes only what did not finish."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from src.application.tasks import (  # pyright: ignore[reportPrivateUsage]
    _initial_state,
    _run_graph,
)
from src.domain.action import ActionType
from src.infrastructure.checkpoints import serializer
from tests.factories import ACTION_ID, STUDENT_ID

_FINDINGS = (
    '[{"section": "Wstęp", "description": "Brak hipotez", '
    '"severity": "critical", "suggestion": "-", "quote": ""}]'
)
_REVIEW = (
    '{"scores": [{"criteria": "Struktura", "points": 4}], '
    '"review_text": "Recenzja.", "recommendation": "Zwrócić do poprawy"}'
)


class WorkerDied(BaseException):
    """Stands in for the process being killed: no node catches it."""


@pytest.fixture(autouse=True)
def no_status_writes() -> Iterator[None]:
    with (
        patch("src.application.tasks.record_task_status"),
        patch("src.application.tasks.record_task_progress"),
    ):
        yield


@pytest.fixture
def saver() -> Iterator[InMemorySaver]:
    memory = InMemorySaver(serde=serializer())

    @contextmanager
    def _open() -> Iterator[InMemorySaver]:
        yield memory

    with (
        patch("src.application.tasks.open_checkpointer", _open),
        patch(
            "src.application.tasks.delete_checkpoints",
            side_effect=lambda ids: [memory.delete_thread(i) for i in ids],
        ),
    ):
        yield memory


def _llm(calls: list[str], die_in_review: bool) -> MagicMock:
    def _answer(messages: list[Any], **_: Any) -> AIMessage:  # noqa: ANN401
        system = str(messages[0].content)
        if "formal thesis review" in system:
            calls.append("review")
            if die_in_review:
                raise WorkerDied
            return AIMessage(content=_REVIEW)
        calls.append("analysis")
        return AIMessage(content=_FINDINGS)

    llm = MagicMock()
    llm.invoke.side_effect = _answer
    return llm


def _run(task_id: str, llm: MagicMock) -> dict[str, Any]:
    state = _initial_state(
        ACTION_ID,
        ActionType.GENERATE_REVIEW,
        STUDENT_ID,
        {"text": "Wstęp. Zakończenie.", "guidelines": "rules"},
        "qwen3:30b-a3b",
        "pl",
    )
    for module in ("structure", "methodology", "requirements", "review"):
        patch(f"src.application.nodes.{module}.get_llm", return_value=llm).start()
    try:
        return _run_graph(task_id, state)
    finally:
        patch.stopall()


def test_a_retry_resumes_after_the_steps_already_done(saver: InMemorySaver) -> None:
    calls: list[str] = []

    with pytest.raises(WorkerDied):
        _run("task-1", _llm(calls, die_in_review=True))
    assert calls.count("analysis") == 3

    # The same task id, as a Celery retry or redelivery would have.
    payload = _run("task-1", _llm(calls, die_in_review=False))

    # The three analyses ran once in all; only the review ran again.
    assert calls.count("analysis") == 3
    assert calls.count("review") == 2
    assert payload["output"]["recommendation"] == "Zwrócić do poprawy"
    assert payload["findings"][0]["description"] == "Brak hipotez"


def test_checkpoints_are_deleted_once_the_run_has_an_outcome(
    saver: InMemorySaver,
) -> None:
    _run("task-2", _llm([], die_in_review=False))

    assert saver.get_tuple({"configurable": {"thread_id": "task-2"}}) is None


def test_a_different_task_starts_from_scratch(saver: InMemorySaver) -> None:
    calls: list[str] = []
    with pytest.raises(WorkerDied):
        _run("task-3", _llm(calls, die_in_review=True))

    _run("task-4", _llm(calls, die_in_review=False))

    assert calls.count("analysis") == 6


# ---------- the promoter's pause ----------

_TWO_FINDINGS = (
    '[{"section": "Wstęp", "description": "Brak hipotez", '
    '"severity": "critical", "suggestion": "-", "quote": ""}, '
    '{"section": "Bibliografia", "description": "Za mało źródeł", '
    '"severity": "major", "suggestion": "-", "quote": ""}]'
)


def _paused_run(
    task_id: str, calls: list[str], review_prompts: list[str]
) -> dict[str, Any]:
    def _answer(messages: list[Any], **_: Any) -> AIMessage:  # noqa: ANN401
        system = str(messages[0].content)
        if "formal thesis review" in system:
            calls.append("review")
            review_prompts.append(str(messages[1].content))
            return AIMessage(content=_REVIEW)
        calls.append("analysis")
        # One analysis finds both; the others find nothing.
        return AIMessage(content=_TWO_FINDINGS if "structure" in system[:200] else "[]")

    llm = MagicMock()
    llm.invoke.side_effect = _answer
    for module in ("structure", "methodology", "requirements", "review"):
        patch(f"src.application.nodes.{module}.get_llm", return_value=llm).start()
    return {"llm": llm}


def test_the_review_waits_for_the_promoter_and_uses_only_what_they_kept(
    saver: InMemorySaver,
) -> None:
    calls: list[str] = []
    prompts: list[str] = []
    state = _initial_state(
        ACTION_ID,
        ActionType.GENERATE_REVIEW,
        STUDENT_ID,
        {
            "text": "Wstęp. Zakończenie.",
            "guidelines": "rules",
            "promoter_reviews_findings": True,
        },
        "qwen3:30b-a3b",
        "pl",
    )
    _paused_run("task-5", calls, prompts)
    try:
        with patch("src.application.tasks.record_task_status") as status:
            paused = _run_graph("task-5", state)
            assert status.call_args.args[1] == "awaiting_input"
        # Paused before the review, with the findings to choose from.
        assert "review" not in calls
        assert [f["description"] for f in paused["findings"]] == [
            "Brak hipotez",
            "Za mało źródeł",
        ]
        assert saver.get_tuple({"configurable": {"thread_id": "task-5"}}) is not None

        done = _run_graph(
            "task-5",
            None,
            action_type=ActionType.GENERATE_REVIEW,
            decision={"accepted": [1]},
        )
    finally:
        patch.stopall()

    assert calls.count("analysis") == 3  # the analyses did not run again
    assert [f["description"] for f in done["findings"]] == ["Za mało źródeł"]
    assert "Brak hipotez" not in prompts[0]
    assert saver.get_tuple({"configurable": {"thread_id": "task-5"}}) is None


def test_without_checkpoints_the_review_does_not_pause() -> None:
    calls: list[str] = []
    prompts: list[str] = []
    state = _initial_state(
        ACTION_ID,
        ActionType.GENERATE_REVIEW,
        STUDENT_ID,
        {"text": "Wstęp.", "guidelines": "r", "promoter_reviews_findings": True},
        "qwen3:30b-a3b",
        "pl",
    )
    _paused_run("task-6", calls, prompts)
    try:
        payload = _run_graph("task-6", state)
    finally:
        patch.stopall()

    assert "review" in calls
    assert payload["output"]["recommendation"] == "Zwrócić do poprawy"


def test_resuming_a_thread_with_nothing_saved_is_an_error(
    saver: InMemorySaver,
) -> None:
    with pytest.raises(ValueError, match="nothing to resume"):
        _run_graph(
            "never-ran", None, action_type=ActionType.GENERATE_REVIEW, decision={}
        )
