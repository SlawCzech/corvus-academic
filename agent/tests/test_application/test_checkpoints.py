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
