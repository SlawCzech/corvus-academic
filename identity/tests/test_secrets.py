"""Unit tests for SecretService Fernet encryption."""

import pytest
from cryptography.fernet import Fernet, InvalidToken

from src.infrastructure.secrets import SecretService


@pytest.fixture
def svc() -> SecretService:
    return SecretService(Fernet.generate_key())


def test_encrypt_decrypt_roundtrip(svc: SecretService) -> None:
    plain = "sk-ant-api03-super-secret-key-value"
    token = svc.encrypt(plain)
    assert svc.decrypt(token) == plain


def test_encrypted_value_differs_from_plain(svc: SecretService) -> None:
    plain = "my-openai-key"
    assert svc.encrypt(plain) != plain


def test_encrypt_returns_str(svc: SecretService) -> None:
    result = svc.encrypt("test")
    assert isinstance(result, str)


def test_decrypt_returns_str(svc: SecretService) -> None:
    token = svc.encrypt("hello")
    result = svc.decrypt(token)
    assert isinstance(result, str)


def test_different_keys_cannot_cross_decrypt() -> None:
    svc_a = SecretService(Fernet.generate_key())
    svc_b = SecretService(Fernet.generate_key())
    token = svc_a.encrypt("secret")
    with pytest.raises(InvalidToken):
        svc_b.decrypt(token)


def test_encrypt_empty_string(svc: SecretService) -> None:
    token = svc.encrypt("")
    assert svc.decrypt(token) == ""
