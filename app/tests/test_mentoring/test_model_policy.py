"""The admin's model allowlist, without a database or an agent."""

import pytest

from src.mentoring.domain.model_policy import (
    ModelNotAllowedError,
    ModelPolicy,
    ModelPolicyError,
    ModelSetting,
)


def test_with_nothing_chosen_an_empty_request_goes_to_the_agents_default() -> None:
    policy = ModelPolicy(settings=[])

    assert policy.resolve(None) is None
    assert policy.resolve("") is None


def test_with_nothing_chosen_a_named_model_is_refused() -> None:
    with pytest.raises(ModelNotAllowedError):
        ModelPolicy(settings=[]).resolve("gemma4:12b")


def test_the_admins_default_replaces_an_empty_request() -> None:
    policy = ModelPolicy(settings=[ModelSetting("gemma4:12b", True, True)])

    assert policy.resolve("") == "gemma4:12b"


def test_only_enabled_models_resolve() -> None:
    policy = ModelPolicy(
        settings=[
            ModelSetting("gemma4:12b", True, True),
            ModelSetting("llama3.1:latest", True, False),
            ModelSetting("qwen3:32b", False, False),
        ]
    )

    assert policy.resolve("llama3.1:latest") == "llama3.1:latest"
    with pytest.raises(ModelNotAllowedError):
        policy.resolve("qwen3:32b")


def test_the_server_default_counts_as_enabled_until_the_admin_picks_one() -> None:
    policy = ModelPolicy(settings=[], server_default="qwen3:30b-a3b")

    assert policy.default == "qwen3:30b-a3b"
    assert policy.is_enabled("qwen3:30b-a3b")
    with pytest.raises(ModelPolicyError):
        policy.check_disable("qwen3:30b-a3b")


def test_once_the_admin_picks_a_default_the_server_one_is_just_another_model() -> None:
    policy = ModelPolicy(
        settings=[ModelSetting("gemma4:12b", True, True)],
        server_default="qwen3:30b-a3b",
    )

    assert policy.default == "gemma4:12b"
    assert not policy.is_enabled("qwen3:30b-a3b")
    policy.check_disable("qwen3:30b-a3b")  # no longer the default — allowed
