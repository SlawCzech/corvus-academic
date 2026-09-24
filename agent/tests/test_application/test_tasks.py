"""Tests for the run_action Celery task."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from celery.exceptions import Retry

from src.application.tasks import _result_payload, run_action
from src.domain.action import ActionType, TaskStatus
from src.domain.analysis import Finding, FindingSeverity, FindingSource
from src.infrastructure.celery_app import celery_app
from src.infrastructure.llm_factory import current_credentials
from tests.factories import ACTION_ID, STUDENT_ID

_TEXT = "Chapter 1: Introduction. Chapter 2: Methodology."
_GUIDELINES = "## 4. CRITICAL: brak celu pracy."
_METADATA: dict[str, Any] = {
    "author": "Jan Kowalski",
    "title": "Test Thesis",
    "year": 2024,
    "field_of_study": "Computer Science",
    "thesis_type": "bachelor",
    "review_tone": "auto",
}


@pytest.fixture(autouse=True)
def _eager_mode() -> None:  # pyright: ignore[reportUnusedFunction]
    """Execute Celery tasks synchronously in tests."""
    celery_app.conf.update(task_always_eager=True, task_eager_propagates=True)


@pytest.fixture(autouse=True)
def status_writes() -> Any:  # noqa: ANN401
    """Keep status writes off the real database; assert on them instead."""
    with patch("src.application.tasks.record_task_status") as mock:
        yield mock


def _final_state(**overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    state: dict[str, Any] = {
        "action_id": ACTION_ID,
        "action_type": ActionType.GENERATE_REVIEW,
        "student_id": STUDENT_ID,
        "context": {"text": _TEXT, "guidelines": _GUIDELINES},
        "findings": [],
        "scores": [],
        "output": None,
        "status": "analyzed",
        "error": None,
    }
    state.update(overrides)
    return state


def _mock_graph(state: dict[str, Any] | None = None) -> MagicMock:
    graph = MagicMock()
    graph.invoke.return_value = state if state is not None else _final_state()
    return graph


# ---------- generic action runner ----------


def test_run_action_builds_state_from_its_arguments() -> None:
    graph = _mock_graph()
    context = {"field_of_study": "Ekonomia", "detail": "coś o instytucjach"}

    with patch(
        "src.application.tasks.build_action_graph", return_value=graph
    ) as builder:
        run_action.apply(
            args=(ACTION_ID, ActionType.PROPOSE_TOPIC, STUDENT_ID, context)
        )

    assert builder.call_args.args[0] == ActionType.PROPOSE_TOPIC
    call_state: dict[str, Any] = graph.invoke.call_args[0][0]
    assert call_state["action_id"] == ACTION_ID
    assert call_state["student_id"] == STUDENT_ID
    assert call_state["context"] == context
    assert call_state["output"] is None
    assert call_state["error"] is None


def test_run_action_returns_the_actions_output() -> None:
    proposal = {"topics": [{"title": "Instytucje a wzrost"}], "recommended": 0}
    graph = _mock_graph(
        _final_state(action_type=ActionType.PROPOSE_TOPIC, output=proposal)
    )

    with patch("src.application.tasks.build_action_graph", return_value=graph):
        result = run_action.apply(
            args=(ACTION_ID, ActionType.PROPOSE_TOPIC, STUDENT_ID, {})
        )

    payload: dict[str, Any] = result.get()
    assert payload["output"] == proposal
    assert payload["action_id"] == ACTION_ID
    # The context is an input; it never travels back out.
    assert "context" not in payload


def test_run_action_records_running_then_completed(
    status_writes: MagicMock,
) -> None:
    with patch("src.application.tasks.build_action_graph", return_value=_mock_graph()):
        run_action.apply(args=(ACTION_ID, ActionType.GENERATE_REVIEW, STUDENT_ID, {}))

    statuses = [call.args[1] for call in status_writes.call_args_list]
    assert statuses == [TaskStatus.RUNNING, TaskStatus.COMPLETED]


def test_node_error_is_recorded_as_a_failed_task(status_writes: MagicMock) -> None:
    """A node that could not produce anything is a failure, not a done task."""
    graph = _mock_graph(_final_state(error="Ollama unreachable"))

    with patch("src.application.tasks.build_action_graph", return_value=graph):
        run_action.apply(args=(ACTION_ID, ActionType.GENERATE_REVIEW, STUDENT_ID, {}))

    last = status_writes.call_args_list[-1]
    assert last.args[1] == TaskStatus.FAILED
    assert last.kwargs["error"] == "Ollama unreachable"
    # The partial payload is still stored — it says which node got how far.
    assert last.kwargs["result"]["error"] == "Ollama unreachable"


def test_a_review_written_despite_a_failed_branch_completes_and_says_so(
    status_writes: MagicMock,
) -> None:
    """One branch down still leaves a review — keep it, and keep why it is thin."""
    graph = _mock_graph(
        _final_state(
            output={"summary": "Praca poprawna.", "recommendation": "Dopuścić"},
            node_errors=["structure: Ollama timeout"],
        )
    )

    with patch("src.application.tasks.build_action_graph", return_value=graph):
        run_action.apply(args=(ACTION_ID, ActionType.GENERATE_REVIEW, STUDENT_ID, {}))

    last = status_writes.call_args_list[-1]
    assert last.args[1] == TaskStatus.COMPLETED
    assert last.kwargs["result"]["node_errors"] == ["structure: Ollama timeout"]


def test_analysis_that_failed_with_nothing_to_show_is_a_failed_task(
    status_writes: MagicMock,
) -> None:
    """A lone evaluate_methodology whose node broke produced nothing at all."""
    graph = _mock_graph(
        _final_state(
            action_type=ActionType.EVALUATE_METHODOLOGY,
            node_errors=["methodology: Connection refused"],
        )
    )

    with patch("src.application.tasks.build_action_graph", return_value=graph):
        run_action.apply(
            args=(ACTION_ID, ActionType.EVALUATE_METHODOLOGY, STUDENT_ID, {})
        )

    last = status_writes.call_args_list[-1]
    assert last.args[1] == TaskStatus.FAILED
    assert last.kwargs["error"] == "methodology: Connection refused"


def test_run_action_retries_when_the_graph_raises() -> None:
    with patch("src.application.tasks.build_action_graph") as builder:
        builder.side_effect = Exception("Graph failed")
        with pytest.raises(Retry):
            run_action.apply(
                args=(ACTION_ID, ActionType.GENERATE_REVIEW, STUDENT_ID, {}),
                throw=True,
            )


def test_last_attempt_records_failure(status_writes: MagicMock) -> None:
    """When retries are exhausted the failure is persisted with its message."""
    with patch("src.application.tasks.build_action_graph") as builder:
        builder.side_effect = Exception("Graph failed")
        with pytest.raises(Exception, match="Graph failed"):
            run_action.apply(
                args=(ACTION_ID, ActionType.GENERATE_REVIEW, STUDENT_ID, {}),
                retries=3,
                throw=True,
            )

    last = status_writes.call_args_list[-1]
    assert last.args[1] == TaskStatus.FAILED
    assert "Graph failed" in last.kwargs["error"]


def test_intermediate_failure_stays_running(status_writes: MagicMock) -> None:
    """A failure that will be retried must not be recorded as final."""
    with patch("src.application.tasks.build_action_graph") as builder:
        builder.side_effect = Exception("Graph failed")
        with pytest.raises(Retry):
            run_action.apply(
                args=(ACTION_ID, ActionType.GENERATE_REVIEW, STUDENT_ID, {}),
                throw=True,
            )

    statuses = [call.args[1] for call in status_writes.call_args_list]
    assert statuses == [TaskStatus.RUNNING]


# ---------- payload shaping ----------


def test_result_payload_promotes_review_fields() -> None:
    """summary and recommendation are lifted so the frontend can read them."""
    payload = _result_payload(
        _final_state(
            output={
                "summary": "Praca spełnia wymogi.",
                "recommendation": "Dopuścić do obrony",
                "total_percentage": 80.0,
            }
        )
    )

    assert payload["summary"] == "Praca spełnia wymogi."
    assert payload["recommendation"] == "Dopuścić do obrony"
    assert payload["output"]["total_percentage"] == 80.0


def test_result_payload_leaves_other_actions_output_alone() -> None:
    """Only review-shaped output has fields worth promoting."""
    payload = _result_payload(
        _final_state(
            action_type=ActionType.PROPOSE_TOPIC,
            output={"topics": [], "recommended": 0},
        )
    )

    assert "summary" not in payload
    assert payload["output"] == {"topics": [], "recommended": 0}


def test_result_payload_keeps_which_analysis_raised_each_finding() -> None:
    """The source survives into the stored JSON as a plain string."""
    finding = Finding(
        section="Wnioski",
        description="Brak wniosków",
        severity=FindingSeverity.CRITICAL,
        suggestion="Dodaj wnioski.",
        source=FindingSource.REQUIREMENTS,
    )

    payload = json.loads(json.dumps(_result_payload(_final_state(findings=[finding]))))

    assert payload["findings"][0]["source"] == "requirements"


# ---------- guidelines ----------


def test_review_actions_get_the_university_requirements() -> None:
    """Guideline text is agent-owned static data, not something `app` ships."""
    graph = _mock_graph()

    with (
        patch("src.application.tasks.build_action_graph", return_value=graph),
        patch(
            "src.application.tasks.retrieve_relevant_guidelines",
            return_value=_GUIDELINES,
        ) as retrieve,
    ):
        run_action.apply(
            args=(
                ACTION_ID,
                ActionType.EVALUATE_METHODOLOGY,
                STUDENT_ID,
                {"text": _TEXT, "thesis_type": "master_article"},
            )
        )

    # Retrieved against the thesis, so both the type and the text are needed.
    retrieve.assert_called_once_with("master_article", _TEXT)
    call_state: dict[str, Any] = graph.invoke.call_args[0][0]
    assert call_state["context"]["guidelines"] == _GUIDELINES


def test_other_actions_are_not_given_guidelines() -> None:
    """Proposing a topic has nothing to check against the requirements."""
    graph = _mock_graph()

    with (
        patch("src.application.tasks.build_action_graph", return_value=graph),
        patch("src.application.tasks.retrieve_relevant_guidelines") as retrieve,
    ):
        run_action.apply(
            args=(ACTION_ID, ActionType.PROPOSE_TOPIC, STUDENT_ID, {"detail": "x"})
        )

    retrieve.assert_not_called()
    call_state: dict[str, Any] = graph.invoke.call_args[0][0]
    assert "guidelines" not in call_state["context"]


# ---------- the user's own key ----------


def test_credentials_are_in_effect_while_the_graph_runs() -> None:
    """Nodes call get_llm() with no arguments, so the key travels out of band."""
    seen: list[Any] = []

    def _capture(state: dict[str, Any]) -> dict[str, Any]:
        seen.append(current_credentials())
        return _final_state()

    graph = MagicMock()
    graph.invoke.side_effect = _capture

    with patch("src.application.tasks.build_action_graph", return_value=graph):
        run_action.apply(
            args=(ACTION_ID, ActionType.PROPOSE_TOPIC, STUDENT_ID, {}),
            kwargs={"provider": "claude", "api_key": "sk-user-key"},
        )

    assert seen[0] is not None
    assert seen[0].provider == "claude"
    assert seen[0].api_key == "sk-user-key"
    # …and only while it runs.
    assert current_credentials() is None


def test_the_key_never_enters_the_graph_state() -> None:
    """State is what gets serialised into the stored result."""
    graph = _mock_graph()

    with patch("src.application.tasks.build_action_graph", return_value=graph):
        run_action.apply(
            args=(
                ACTION_ID,
                ActionType.PROPOSE_TOPIC,
                STUDENT_ID,
                {"detail": "coś"},
            ),
            kwargs={"provider": "claude", "api_key": "sk-user-key"},
        )

    state: dict[str, Any] = graph.invoke.call_args[0][0]
    assert "sk-user-key" not in json.dumps(state, default=str)


def test_the_key_never_reaches_the_stored_result(status_writes: MagicMock) -> None:
    graph = _mock_graph()

    with patch("src.application.tasks.build_action_graph", return_value=graph):
        result = run_action.apply(
            args=(ACTION_ID, ActionType.PROPOSE_TOPIC, STUDENT_ID, {}),
            kwargs={"provider": "claude", "api_key": "sk-user-key"},
        )

    assert "sk-user-key" not in json.dumps(result.get(), default=str)
    stored = status_writes.call_args_list[-1].kwargs["result"]
    assert "sk-user-key" not in json.dumps(stored, default=str)


def test_without_a_key_nothing_is_in_effect() -> None:
    """Ollama is the fallback: no key, no credentials, no change of model."""
    seen: list[Any] = []

    def _capture(state: dict[str, Any]) -> dict[str, Any]:
        seen.append(current_credentials())
        return _final_state()

    graph = MagicMock()
    graph.invoke.side_effect = _capture

    with patch("src.application.tasks.build_action_graph", return_value=graph):
        run_action.apply(args=(ACTION_ID, ActionType.PROPOSE_TOPIC, STUDENT_ID, {}))

    assert seen == [None]
