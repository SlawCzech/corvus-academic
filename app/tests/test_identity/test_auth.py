"""Unit tests for JWT token creation and verification."""

import os
import uuid
from datetime import UTC, datetime

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-key-that-is-long-enough-32ch")

from src.identity.application.auth import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    verify_access_token,
    verify_refresh_token,
)
from src.identity.domain.user import Role, User


@pytest.fixture
def admin_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="admin@test.com",
        role=Role.ADMIN,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def promotor_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="promotor@test.com",
        role=Role.PROMOTOR,
        created_at=datetime.now(UTC),
    )


def test_create_access_token_returns_string(admin_user: User) -> None:
    token = create_access_token(admin_user)
    assert isinstance(token, str)
    assert len(token) > 0


def test_access_token_roundtrip_admin(admin_user: User) -> None:
    token = create_access_token(admin_user)
    recovered = verify_access_token(token)
    assert recovered.id == admin_user.id
    assert recovered.email == admin_user.email
    assert recovered.role == Role.ADMIN


def test_access_token_roundtrip_promotor(promotor_user: User) -> None:
    token = create_access_token(promotor_user)
    recovered = verify_access_token(token)
    assert recovered.role == Role.PROMOTOR


def test_verify_access_token_invalid_raises() -> None:
    with pytest.raises(ValueError, match="Invalid token"):
        verify_access_token("not.a.valid.jwt")


def test_verify_access_token_tampered_raises(admin_user: User) -> None:
    token = create_access_token(admin_user)
    tampered = token[:-3] + "xxx"
    with pytest.raises(ValueError):
        verify_access_token(tampered)


def test_verify_access_token_empty_raises() -> None:
    with pytest.raises(ValueError):
        verify_access_token("")


def test_refresh_token_rejected_as_access(admin_user: User) -> None:
    refresh, _jti = create_refresh_token(admin_user)
    with pytest.raises(ValueError, match="Not an access token"):
        verify_access_token(refresh)


def test_create_refresh_token_returns_tuple(admin_user: User) -> None:
    token, jti = create_refresh_token(admin_user)
    assert isinstance(token, str)
    assert isinstance(jti, str)
    assert len(token) > 0
    assert len(jti) > 0


def test_refresh_token_roundtrip(admin_user: User) -> None:
    token, jti = create_refresh_token(admin_user)
    user_id, recovered_jti = verify_refresh_token(token)
    assert user_id == admin_user.id
    assert recovered_jti == jti


def test_access_token_rejected_as_refresh(admin_user: User) -> None:
    access = create_access_token(admin_user)
    with pytest.raises(ValueError, match="Not a refresh token"):
        verify_refresh_token(access)


def test_refresh_tokens_have_unique_jti(admin_user: User) -> None:
    _, jti1 = create_refresh_token(admin_user)
    _, jti2 = create_refresh_token(admin_user)
    assert jti1 != jti2


def test_each_access_token_has_its_own_jti(admin_user: User) -> None:
    first = decode_access_token(create_access_token(admin_user))
    second = decode_access_token(create_access_token(admin_user))
    assert first.jti != second.jti
    assert first.user.id == admin_user.id
    assert first.expires_at > datetime.now(UTC)


def test_access_token_without_jti_is_rejected(admin_user: User) -> None:
    """A token that could never be revoked is not accepted at all."""
    import jwt

    from src.shared.settings import settings

    payload = {
        "sub": str(admin_user.id),
        "email": admin_user.email,
        "role": str(admin_user.role),
        "type": "access",
        "exp": datetime.now(UTC).timestamp() + 60,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    with pytest.raises(ValueError, match="jti"):
        verify_access_token(token)
