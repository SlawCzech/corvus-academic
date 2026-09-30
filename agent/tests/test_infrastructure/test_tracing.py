"""Tests for graph-run tracing: off by default, never in the way of an action."""

from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure import tracing
from src.infrastructure.settings import settings


@pytest.fixture
def langfuse_configured(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(settings, "langfuse_base_url", "http://langfuse:3000")
    monkeypatch.setattr(settings, "langfuse_public_key", "pk-lf-test")
    monkeypatch.setattr(settings, "langfuse_secret_key", "sk-lf-test")
    tracing._client.cache_clear()  # pyright: ignore[reportPrivateUsage]
    yield
    tracing._client.cache_clear()  # pyright: ignore[reportPrivateUsage]


def _config(**overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    kwargs: dict[str, Any] = {
        "action_type": "generate_review",
        "action_id": "a-1",
        "student_id": "s-1",
        "model": "qwen3:30b-a3b",
        "task_id": "t-1",
    }
    kwargs.update(overrides)
    return dict(tracing.run_config(**kwargs))


def test_tracing_is_off_without_configuration() -> None:
    assert not tracing.tracing_enabled()
    assert _config()["callbacks"] == []


def test_run_config_names_the_run_and_groups_by_student() -> None:
    config = _config()

    assert config["run_name"] == "action:generate_review"
    assert config["tags"] == ["generate_review", "qwen3:30b-a3b"]
    # One Langfuse session per student: their whole AI history in one view.
    assert config["metadata"]["langfuse_session_id"] == "s-1"
    assert config["metadata"]["task_id"] == "t-1"


def test_configured_tracing_attaches_a_langfuse_callback(
    langfuse_configured: None,
) -> None:
    with patch("langfuse.Langfuse") as client:
        callbacks = _config()["callbacks"]

    client.assert_called_once_with(
        public_key="pk-lf-test",
        secret_key="sk-lf-test",
        base_url="http://langfuse:3000",
    )
    assert len(callbacks) == 1
    assert type(callbacks[0]).__module__.startswith("langfuse")


def test_a_broken_tracing_setup_leaves_the_run_untraced(
    langfuse_configured: None,
) -> None:
    with patch("langfuse.Langfuse", side_effect=RuntimeError("no server")):
        assert _config()["callbacks"] == []


def test_flush_is_a_no_op_when_off() -> None:
    with patch.object(tracing, "_client") as client:
        tracing.flush()
    client.assert_not_called()


def test_flush_failure_is_swallowed(langfuse_configured: None) -> None:
    broken = MagicMock()
    broken.flush.side_effect = RuntimeError("down")
    with patch.object(tracing, "_client", return_value=broken):
        tracing.flush()  # must not raise
