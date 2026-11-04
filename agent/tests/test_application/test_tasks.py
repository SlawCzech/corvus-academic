"""Tests for the run_action Celery task."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from celery.exceptions import Retry

from src.application.tasks import _result_payload, run_action
from src.domain.action import ActionErrorCode, ActionType, TaskStatus
from src.domain.analysis import Finding, FindingSeverity, FindingSource
from src.infrastructure.celery_app import celery_app
from src.infrastructure.key_transit import seal
from src.infrastructure.llm_factory import current_credentials
from src.infrastructure.provider_errors import ProviderAccountError
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


@pytest.fixture(autouse=True)
def progress_writes() -> Any:  # noqa: ANN401
    """Progress writes too."""
    with patch("src.application.tasks.record_task_progress") as mock:
        yield mock


@pytest.fixture(autouse=True)
def usage_writes() -> Any:  # noqa: ANN401
    """And usage writes."""
    with patch("src.application.tasks.record_task_usage") as mock:
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


def _streams_through_invoke(graph: MagicMock) -> MagicMock:
    """Make ``stream`` yield what ``invoke`` returns, as its final values.

    The task streams the graph; the tests describe it by its ``invoke`` —
    return value or side effect — and assert on ``invoke``'s call args.
    """
    graph.get_graph.return_value.nodes = {"__start__": 0, "node": 0, "__end__": 0}

    def _stream(state: Any, config: Any = None, stream_mode: Any = None) -> Any:  # noqa: ANN401
        final = graph.invoke(state, config=config)
        return iter([("updates", {"node": {}}), ("values", final)])

    graph.stream.side_effect = _stream
    return graph


def _mock_graph(state: dict[str, Any] | None = None) -> MagicMock:
    graph = MagicMock()
    graph.invoke.return_value = state if state is not None else _final_state()
    return _streams_through_invoke(graph)


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


def test_run_action_invokes_the_graph_with_a_traceable_config() -> None:
    """The run is named and grouped by student, so traces can be found."""
    graph = _mock_graph()

    with patch("src.application.tasks.build_action_graph", return_value=graph):
        run_action.apply(
            args=(ACTION_ID, ActionType.PROPOSE_TOPIC, STUDENT_ID, {}),
            task_id="task-trace",
        )

    config: dict[str, Any] = graph.invoke.call_args.kwargs["config"]
    assert config["run_name"] == f"action:{ActionType.PROPOSE_TOPIC}"
    assert config["metadata"]["langfuse_session_id"] == STUDENT_ID
    assert config["metadata"]["task_id"] == "task-trace"


def test_progress_is_recorded_as_each_node_finishes(progress_writes: Any) -> None:  # noqa: ANN401
    """The graph's steps up front, then one write per finished node."""
    graph = _mock_graph()
    graph.get_graph.return_value.nodes = {
        "__start__": 0,
        "analyze_structure": 0,
        "verify": 0,
        "__end__": 0,
    }
    graph.stream.side_effect = lambda state, config=None, stream_mode=None: iter(
        [
            ("updates", {"analyze_structure": {}}),
            ("values", _final_state()),
            ("updates", {"verify": {}}),
            ("values", _final_state()),
        ]
    )

    with patch("src.application.tasks.build_action_graph", return_value=graph):
        run_action.apply(
            args=(ACTION_ID, ActionType.GENERATE_REVIEW, STUDENT_ID, {}),
            task_id="task-progress",
        )

    written = [c.args[1] for c in progress_writes.call_args_list]
    steps = ["analyze_structure", "verify"]
    assert written == [
        {"steps": steps, "done": []},
        {"steps": steps, "done": ["analyze_structure"]},
        {"steps": steps, "done": ["analyze_structure", "verify"]},
    ]


def _spends_tokens(graph: MagicMock, tokens: int, then: Any = None) -> None:  # noqa: ANN401
    """Make the graph report one model call's usage to the run's callbacks."""
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration, LLMResult

    def _invoke(state: Any, config: Any = None) -> Any:  # noqa: ANN401
        message = AIMessage(
            content="",
            usage_metadata={
                "input_tokens": tokens,
                "output_tokens": 0,
                "total_tokens": tokens,
            },
            response_metadata={"model_name": "claude-sonnet-5-5"},
        )
        result = LLMResult(generations=[[ChatGeneration(message=message)]])
        for callback in config["callbacks"]:
            if hasattr(callback, "on_llm_end"):
                callback.on_llm_end(result)
        if isinstance(then, Exception):
            raise then
        return _final_state()

    graph.invoke.side_effect = _invoke


def test_tokens_are_recorded_before_the_final_status(
    usage_writes: MagicMock, status_writes: MagicMock
) -> None:
    """`app` stops asking once the task is over — the count has to be there."""
    graph = _mock_graph()
    _spends_tokens(graph, 120)
    calls = MagicMock()
    calls.attach_mock(usage_writes, "usage")
    calls.attach_mock(status_writes, "status")

    with patch("src.application.tasks.build_action_graph", return_value=graph):
        run_action.apply(
            args=(ACTION_ID, ActionType.PROPOSE_TOPIC, STUDENT_ID, {}),
            task_id="task-usage",
        )

    task_id, usage = usage_writes.call_args.args
    assert task_id == "task-usage"
    assert usage["total_tokens"] == 120
    names = [c[0] for c in calls.mock_calls]
    assert names.index("usage") < len(names) - 1
    assert calls.mock_calls[-1].args[1] == TaskStatus.COMPLETED


def test_a_run_that_raises_still_records_what_it_spent(
    usage_writes: MagicMock,
) -> None:
    graph = _mock_graph()
    _spends_tokens(graph, 50, then=RuntimeError("model went away"))

    with (
        patch("src.application.tasks.build_action_graph", return_value=graph),
        pytest.raises(Exception),  # noqa: B017 — retry or the error itself
    ):
        run_action.apply(
            args=(ACTION_ID, ActionType.PROPOSE_TOPIC, STUDENT_ID, {}),
            task_id="task-raised",
        ).get()

    assert usage_writes.call_args.args[1]["total_tokens"] == 50


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
    graph = _mock_graph(_final_state(error="provider unreachable"))

    with patch("src.application.tasks.build_action_graph", return_value=graph):
        run_action.apply(args=(ACTION_ID, ActionType.GENERATE_REVIEW, STUDENT_ID, {}))

    last = status_writes.call_args_list[-1]
    assert last.args[1] == TaskStatus.FAILED
    assert last.kwargs["error"] == "provider unreachable"
    # The partial payload is still stored — it says which node got how far.
    assert last.kwargs["result"]["error"] == "provider unreachable"


def test_a_review_written_despite_a_failed_branch_completes_and_says_so(
    status_writes: MagicMock,
) -> None:
    """One branch down still leaves a review — keep it, and keep why it is thin."""
    graph = _mock_graph(
        _final_state(
            output={"summary": "Praca poprawna.", "recommendation": "Dopuścić"},
            node_errors=["structure: provider timeout"],
        )
    )

    with patch("src.application.tasks.build_action_graph", return_value=graph):
        run_action.apply(args=(ACTION_ID, ActionType.GENERATE_REVIEW, STUDENT_ID, {}))

    last = status_writes.call_args_list[-1]
    assert last.args[1] == TaskStatus.COMPLETED
    assert last.kwargs["result"]["node_errors"] == ["structure: provider timeout"]


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
            "src.application.tasks.load_guidelines",
            return_value=_GUIDELINES,
        ) as load,
    ):
        run_action.apply(
            args=(
                ACTION_ID,
                ActionType.EVALUATE_METHODOLOGY,
                STUDENT_ID,
                {"text": _TEXT, "thesis_type": "master_article"},
            )
        )

    load.assert_called_once_with("master_article")
    call_state: dict[str, Any] = graph.invoke.call_args[0][0]
    assert call_state["context"]["guidelines"] == _GUIDELINES


def test_other_actions_are_not_given_guidelines() -> None:
    """Proposing a topic has nothing to check against the requirements."""
    graph = _mock_graph()

    with (
        patch("src.application.tasks.build_action_graph", return_value=graph),
        patch("src.application.tasks.load_guidelines") as load,
    ):
        run_action.apply(
            args=(ACTION_ID, ActionType.PROPOSE_TOPIC, STUDENT_ID, {"detail": "x"})
        )

    load.assert_not_called()
    call_state: dict[str, Any] = graph.invoke.call_args[0][0]
    assert "guidelines" not in call_state["context"]


# ---------- the user's own key ----------


def test_credentials_are_in_effect_while_the_graph_runs() -> None:
    """Nodes call get_llm() with no arguments, so the key travels out of band."""
    seen: list[Any] = []

    def _capture(state: dict[str, Any], config: Any = None) -> dict[str, Any]:  # noqa: ANN401
        seen.append(current_credentials())
        return _final_state()

    graph = MagicMock()
    graph.invoke.side_effect = _capture
    _streams_through_invoke(graph)

    with patch("src.application.tasks.build_action_graph", return_value=graph):
        run_action.apply(
            args=(ACTION_ID, ActionType.PROPOSE_TOPIC, STUDENT_ID, {}),
            kwargs={"provider": "claude", "sealed_api_key": seal("sk-user-key")},
        )

    assert seen[0] is not None
    assert seen[0].provider == "claude"
    assert seen[0].api_key == "sk-user-key"
    # …and only while it runs.
    assert current_credentials() is None


def test_a_key_that_will_not_open_fails_the_task_at_once(
    status_writes: MagicMock,
) -> None:
    """Retrying cannot fix it, and running locally instead was not chosen."""
    graph = _mock_graph()

    with (
        patch("src.application.tasks.build_action_graph", return_value=graph),
        pytest.raises(ValueError, match="JWT_SECRET"),
    ):
        run_action.apply(
            args=(ACTION_ID, ActionType.PROPOSE_TOPIC, STUDENT_ID, {}),
            kwargs={"provider": "claude", "sealed_api_key": "not-a-sealed-key"},
            task_id="task-unsealable",
        ).get()

    graph.invoke.assert_not_called()
    assert status_writes.call_args.args[:2] == ("task-unsealable", TaskStatus.FAILED)


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
            kwargs={"provider": "claude", "sealed_api_key": seal("sk-user-key")},
        )

    state: dict[str, Any] = graph.invoke.call_args[0][0]
    assert "sk-user-key" not in json.dumps(state, default=str)


def test_the_key_never_reaches_the_stored_result(status_writes: MagicMock) -> None:
    graph = _mock_graph()

    with patch("src.application.tasks.build_action_graph", return_value=graph):
        result = run_action.apply(
            args=(ACTION_ID, ActionType.PROPOSE_TOPIC, STUDENT_ID, {}),
            kwargs={"provider": "claude", "sealed_api_key": seal("sk-user-key")},
        )

    assert "sk-user-key" not in json.dumps(result.get(), default=str)
    stored = status_writes.call_args_list[-1].kwargs["result"]
    assert "sk-user-key" not in json.dumps(stored, default=str)


def test_without_a_key_nothing_is_in_effect() -> None:
    """No key, no credentials: the nodes fail rather than run on another's."""
    seen: list[Any] = []

    def _capture(state: dict[str, Any], config: Any = None) -> dict[str, Any]:  # noqa: ANN401
        seen.append(current_credentials())
        return _final_state()

    graph = MagicMock()
    graph.invoke.side_effect = _capture
    _streams_through_invoke(graph)

    with patch("src.application.tasks.build_action_graph", return_value=graph):
        run_action.apply(args=(ACTION_ID, ActionType.PROPOSE_TOPIC, STUDENT_ID, {}))

    assert seen == [None]


# ---------- the provider's account ----------


def _account_problem(code: ActionErrorCode, retry_after: float | None = None) -> Any:  # noqa: ANN401
    return ProviderAccountError(code, "anthropic", "the provider said no", retry_after)


def test_no_credits_fails_at_once_without_retrying(status_writes: MagicMock) -> None:
    """Every retry would fail the same way; the promoter should know now."""
    with patch("src.application.tasks.build_action_graph") as builder:
        builder.side_effect = _account_problem(ActionErrorCode.PROVIDER_NO_CREDITS)
        with pytest.raises(ProviderAccountError):
            run_action.apply(
                args=(ACTION_ID, ActionType.GENERATE_REVIEW, STUDENT_ID, {}),
                throw=True,
            )

    last = status_writes.call_args_list[-1]
    assert last.args[1] == TaskStatus.FAILED
    assert last.kwargs["error_code"] == ActionErrorCode.PROVIDER_NO_CREDITS
    assert "the provider said no" in last.kwargs["error"]


def test_refused_key_fails_at_once_without_retrying(status_writes: MagicMock) -> None:
    with patch("src.application.tasks.build_action_graph") as builder:
        builder.side_effect = _account_problem(ActionErrorCode.PROVIDER_KEY_REJECTED)
        with pytest.raises(ProviderAccountError):
            run_action.apply(
                args=(ACTION_ID, ActionType.GENERATE_REVIEW, STUDENT_ID, {}),
                throw=True,
            )

    last = status_writes.call_args_list[-1]
    assert last.kwargs["error_code"] == ActionErrorCode.PROVIDER_KEY_REJECTED


def test_rate_limit_is_retried_after_what_the_provider_asked(
    status_writes: MagicMock,
) -> None:
    with (
        patch("src.application.tasks.build_action_graph") as builder,
        patch.object(run_action, "retry", side_effect=Retry()) as retry,
    ):
        builder.side_effect = _account_problem(
            ActionErrorCode.PROVIDER_RATE_LIMITED, retry_after=30.0
        )
        with pytest.raises(Retry):
            run_action.apply(
                args=(ACTION_ID, ActionType.GENERATE_REVIEW, STUDENT_ID, {}),
                throw=True,
            )

    assert retry.call_args.kwargs["countdown"] == 30.0
    statuses = [call.args[1] for call in status_writes.call_args_list]
    assert statuses == [TaskStatus.RUNNING]


def test_rate_limit_that_outlasts_the_retries_keeps_its_code(
    status_writes: MagicMock,
) -> None:
    with patch("src.application.tasks.build_action_graph") as builder:
        builder.side_effect = _account_problem(ActionErrorCode.PROVIDER_RATE_LIMITED)
        with pytest.raises(ProviderAccountError):
            run_action.apply(
                args=(ACTION_ID, ActionType.GENERATE_REVIEW, STUDENT_ID, {}),
                retries=3,
                throw=True,
            )

    last = status_writes.call_args_list[-1]
    assert last.args[1] == TaskStatus.FAILED
    assert last.kwargs["error_code"] == ActionErrorCode.PROVIDER_RATE_LIMITED
