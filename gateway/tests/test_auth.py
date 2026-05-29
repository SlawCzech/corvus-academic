"""Unit tests for JWT token creation and verification."""

import os
import uuid

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-key-that-is-long-enough-32ch")

from src.application.auth import create_token, verify_token
from src.domain.user import Role, User


@pytest.fixture
def admin_user() -> User:
    return User(id=uuid.uuid4(), email="admin@test.com", role=Role.ADMIN)


@pytest.fixture
def promotor_user() -> User:
    return User(id=uuid.uuid4(), email="promotor@test.com", role=Role.PROMOTOR)


def test_create_token_returns_string(admin_user: User) -> None:
    token = create_token(admin_user)
    assert isinstance(token, str)
    assert len(token) > 0


def test_roundtrip_admin(admin_user: User) -> None:
    token = create_token(admin_user)
    recovered = verify_token(token)
    assert recovered.id == admin_user.id
    assert recovered.email == admin_user.email
    assert recovered.role == Role.ADMIN


def test_roundtrip_promotor(promotor_user: User) -> None:
    token = create_token(promotor_user)
    recovered = verify_token(token)
    assert recovered.role == Role.PROMOTOR


def test_verify_invalid_token_raises() -> None:
    with pytest.raises(ValueError, match="Invalid token"):
        verify_token("not.a.valid.jwt")


def test_verify_tampered_token_raises(admin_user: User) -> None:
    token = create_token(admin_user)
    # Flip one character in the signature segment
    tampered = token[:-3] + "xxx"
    with pytest.raises(ValueError):
        verify_token(tampered)


def test_verify_empty_token_raises() -> None:
    with pytest.raises(ValueError):
        verify_token("")
