"""Tests for the task lifecycle rules in src/domain/action.py."""

from datetime import UTC, datetime, timedelta

import pytest

from src.domain.action import ABANDONED_AFTER, TaskStatus, is_abandoned

_NOW = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize("status", [TaskStatus.PENDING, TaskStatus.RUNNING])
def test_a_task_that_should_move_and_has_not_is_abandoned(status: TaskStatus) -> None:
    stale = _NOW - ABANDONED_AFTER - timedelta(seconds=1)
    assert is_abandoned(status, stale, _NOW)


def test_a_task_that_moved_recently_is_not() -> None:
    assert not is_abandoned(TaskStatus.RUNNING, _NOW - timedelta(minutes=30), _NOW)


@pytest.mark.parametrize(
    "status",
    [
        TaskStatus.AWAITING_INPUT,
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    ],
)
def test_paused_and_finished_tasks_are_never_abandoned(status: TaskStatus) -> None:
    assert not is_abandoned(status, _NOW - timedelta(days=30), _NOW)


def test_a_time_without_a_zone_is_read_as_utc() -> None:
    naive = (_NOW - timedelta(hours=3)).replace(tzinfo=None)
    assert is_abandoned(TaskStatus.RUNNING, naive, _NOW)
