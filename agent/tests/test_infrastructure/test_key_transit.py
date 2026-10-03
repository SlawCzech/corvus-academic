"""Tests for sealing a provider key for the task queue."""

import pytest
from cryptography.fernet import Fernet

from src.infrastructure import key_transit
from src.infrastructure.key_transit import KeyUnsealError, seal, unseal


def test_a_sealed_key_opens_to_itself() -> None:
    sealed = seal("sk-ant-user-key")

    assert "sk-ant-user-key" not in sealed
    assert unseal(sealed) == "sk-ant-user-key"


def test_each_seal_is_different() -> None:
    """Fernet's IV: two messages with one key do not reveal they share it."""
    assert seal("sk-same") != seal("sk-same")


def test_a_key_sealed_under_another_secret_does_not_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sealed = seal("sk-user-key")
    monkeypatch.setattr(
        key_transit.settings, "jwt_secret", "another-secret-that-is-long-enough-32ch"
    )

    with pytest.raises(KeyUnsealError, match="JWT_SECRET"):
        unseal(sealed)


def test_garbage_does_not_open() -> None:
    with pytest.raises(KeyUnsealError):
        unseal("sk-plain-key-from-an-old-message")
    with pytest.raises(KeyUnsealError):
        unseal(Fernet(Fernet.generate_key()).encrypt(b"x").decode())
