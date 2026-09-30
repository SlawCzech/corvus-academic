"""Tests for the checkpointer's plumbing: off, unreachable, and cleanup."""

from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure import checkpoints
from src.infrastructure.settings import settings


def test_off_means_no_checkpointer() -> None:
    assert not settings.checkpoints_enabled  # tests run with it off
    with checkpoints.open_checkpointer() as saver:
        assert saver is None


def test_an_unreachable_database_means_no_checkpointer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "checkpoints_enabled", True)
    with (
        patch.object(checkpoints, "_connect", side_effect=OSError("refused")),
        checkpoints.open_checkpointer() as saver,
    ):
        assert saver is None


def test_the_checkpointer_uses_the_sync_driver() -> None:
    with patch.object(
        settings, "database_url", "postgresql+asyncpg://u:p@db:5432/corvus"
    ):
        assert checkpoints._conninfo() == "postgresql://u:p@db:5432/corvus"  # pyright: ignore[reportPrivateUsage]


def test_delete_removes_each_thread_and_swallows_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "checkpoints_enabled", True)
    saver = MagicMock()
    opened = MagicMock()
    opened.__enter__.return_value = saver
    with patch.object(checkpoints, "open_checkpointer", return_value=opened):
        checkpoints.delete(["t-1", "", "t-2"])
    assert [c.args[0] for c in saver.delete_thread.call_args_list] == ["t-1", "t-2"]

    saver.delete_thread.side_effect = RuntimeError("db blinked")
    with patch.object(checkpoints, "open_checkpointer", return_value=opened):
        checkpoints.delete(["t-3"])  # must not raise


def test_delete_does_nothing_when_off() -> None:
    with patch.object(checkpoints, "open_checkpointer") as opened:
        checkpoints.delete(["t-1"])
    opened.assert_not_called()


def test_only_domain_types_are_allowed_out_of_a_checkpoint() -> None:
    """Deserialising from the database must not build arbitrary objects."""
    from src.domain.analysis import Finding, FindingSeverity

    serde = checkpoints.serializer()
    finding = Finding("Wstęp", "Brak hipotez", FindingSeverity.CRITICAL, "-")

    assert serde.loads_typed(serde.dumps_typed(finding)) == finding
