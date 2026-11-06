"""Tests for the per-attempt delivery count."""

from unittest.mock import MagicMock, patch

import redis

from src.infrastructure.deliveries import count_delivery


def _redis_returning(count: int) -> MagicMock:
    client = MagicMock()
    client.__enter__.return_value = client
    pipe = client.pipeline.return_value.__enter__.return_value
    pipe.execute.return_value = [count, True]
    return client


def test_returns_the_count_for_this_attempt() -> None:
    client = _redis_returning(3)
    with patch("src.infrastructure.deliveries._client", return_value=client):
        assert count_delivery("run_action", "task-1", 0) == 3

    pipe = client.pipeline.return_value.__enter__.return_value
    pipe.incr.assert_called_once_with("corvus:deliveries:run_action:task-1:0")
    key, ttl = pipe.expire.call_args.args
    assert key == "corvus:deliveries:run_action:task-1:0"
    assert ttl > 60 * 60


def test_each_attempt_has_its_own_count() -> None:
    client = _redis_returning(1)
    with patch("src.infrastructure.deliveries._client", return_value=client):
        count_delivery("run_action", "task-1", 2)

    pipe = client.pipeline.return_value.__enter__.return_value
    assert pipe.incr.call_args.args[0].endswith(":task-1:2")


def test_without_redis_the_count_is_unknown() -> None:
    with patch(
        "src.infrastructure.deliveries._client",
        side_effect=redis.ConnectionError("no redis"),
    ):
        assert count_delivery("run_action", "task-1", 0) is None
