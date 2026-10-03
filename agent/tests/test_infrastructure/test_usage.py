"""Tests for counting the tokens an action spends."""

import operator
from typing import Annotated, Any, TypedDict

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.graph import END, START, StateGraph

from src.infrastructure.usage import Usage, UsageMeter, merge_usage


class _MeteredModel(BaseChatModel):
    """A chat model that reports usage the way a provider does."""

    model_name: str = "claude-sonnet-5-5"
    input_tokens: int = 100
    output_tokens: int = 20

    @property
    def _llm_type(self) -> str:
        return "metered-fake"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> ChatResult:
        message = AIMessage(
            content="ok",
            usage_metadata={
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "total_tokens": self.input_tokens + self.output_tokens,
            },
            response_metadata={"model_name": self.model_name},
        )
        return ChatResult(generations=[ChatGeneration(message=message)])


class _State(TypedDict):
    replies: Annotated[list[str], operator.add]


def _node(model: BaseChatModel) -> Any:  # noqa: ANN401
    def run(state: _State) -> dict[str, list[str]]:
        # No config passed: nodes in this codebase call models exactly so.
        reply = model.invoke("hi")
        return {"replies": [str(reply.content)]}

    return run


def test_counts_every_call_made_inside_the_graph_including_parallel_branches() -> None:
    model = _MeteredModel()
    builder = StateGraph(_State)
    for name in ("structure", "methodology", "requirements"):
        builder.add_node(name, _node(model))
        builder.add_edge(START, name)
        builder.add_edge(name, "review")
    builder.add_node("review", _node(model))
    builder.add_edge("review", END)
    meter = UsageMeter()

    builder.compile().invoke({"replies": []}, config={"callbacks": [meter]})

    assert meter.usage() == {
        "input_tokens": 400,
        "output_tokens": 80,
        "total_tokens": 480,
        "by_model": {
            "claude-sonnet-5-5": {
                "input_tokens": 400,
                "output_tokens": 80,
                "total_tokens": 480,
            }
        },
    }


def test_splits_by_model_and_counts_a_reply_without_a_name() -> None:
    meter = UsageMeter()
    _MeteredModel(model_name="qwen3:30b-a3b").invoke("a", config={"callbacks": [meter]})
    _MeteredModel(model_name="").invoke("b", config={"callbacks": [meter]})

    usage = meter.usage()

    assert usage is not None
    assert set(usage["by_model"]) == {"qwen3:30b-a3b", "unknown"}
    assert usage["total_tokens"] == 240


def test_nothing_counted_is_none() -> None:
    assert UsageMeter().usage() is None


def test_merge_adds_a_resumed_run_to_what_was_stored() -> None:
    first: Usage = {
        "input_tokens": 100,
        "output_tokens": 10,
        "total_tokens": 110,
        "by_model": {
            "claude-sonnet-5-5": {
                "input_tokens": 100,
                "output_tokens": 10,
                "total_tokens": 110,
            }
        },
    }
    second: Usage = {
        "input_tokens": 50,
        "output_tokens": 5,
        "total_tokens": 55,
        "by_model": {
            "claude-sonnet-5-5": {
                "input_tokens": 30,
                "output_tokens": 3,
                "total_tokens": 33,
            },
            "gpt-6.1-sol": {"input_tokens": 20, "output_tokens": 2, "total_tokens": 22},
        },
    }

    merged = merge_usage(first, second)

    assert merged["input_tokens"] == 150
    assert merged["total_tokens"] == 165
    assert merged["by_model"]["claude-sonnet-5-5"]["input_tokens"] == 130
    assert merged["by_model"]["gpt-6.1-sol"]["output_tokens"] == 2


def test_merge_onto_nothing_stored_is_the_run_itself() -> None:
    run: Usage = {
        "input_tokens": 1,
        "output_tokens": 2,
        "total_tokens": 3,
        "by_model": {"m": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}},
    }
    assert merge_usage(None, run) == run
