"""Pydantic request/response models for the identity API.

Each response model that needs building from a domain entity sits next to
the function that builds it — the same pairing ``mentoring/infrastructure/
schemas.py`` uses, and for the same reason.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from src.identity.application.api_keys import SUPPORTED_PROVIDERS
from src.identity.domain.user import Role, User
from src.identity.infrastructure.models import AccessRequestModel, LoginEventModel

# ---------- auth ----------


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105


# ---------- users ----------


class RegisterRequest(BaseModel):
    email: str
    password: str
    role: str = "promotor"

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = {r.value for r in Role}
        if v not in allowed:
            raise ValueError(f"role must be one of {sorted(allowed)}, got {v!r}")
        return v


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    created_at: datetime


def user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id, email=user.email, role=str(user.role), created_at=user.created_at
    )


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# ---------- settings / secrets ----------


class ApiKeyRequest(BaseModel):
    api_key: str = Field(min_length=8)
    provider: str

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        if v not in SUPPORTED_PROVIDERS:
            raise ValueError(
                f"provider must be one of {sorted(SUPPORTED_PROVIDERS)}, got {v!r}"
            )
        return v


class ApiKeyStatusResponse(BaseModel):
    configured: bool
    # Every provider the caller has a key for — one key per provider.
    providers: list[str] = Field(default_factory=list[str])


class ApiKeySavedResponse(ApiKeyStatusResponse):
    # False when the provider could not be asked (offline, down): the key is
    # stored, but nobody has seen it work yet.
    verified: bool


# ---------- admin ----------


class LoginEventResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    email: str
    success: bool
    ip_address: str
    user_agent: str | None
    created_at: datetime


def login_event_response(event: LoginEventModel) -> LoginEventResponse:
    return LoginEventResponse(
        id=event.id,
        user_id=event.user_id,
        email=event.email,
        success=event.success,
        ip_address=event.ip_address,
        user_agent=event.user_agent,
        created_at=event.created_at,
    )


# ---------- access requests ----------


class AccessRequestCreate(BaseModel):
    email: EmailStr


class AccessRequestResponse(BaseModel):
    id: uuid.UUID
    email: str
    created_at: datetime


def access_request_response(req: AccessRequestModel) -> AccessRequestResponse:
    return AccessRequestResponse(id=req.id, email=req.email, created_at=req.created_at)


class TermsStatusResponse(BaseModel):
    # The version in force, and when the caller accepted it (None: not yet).
    current_version: str
    accepted_at: datetime | None


class AcceptTermsRequest(BaseModel):
    # The version the promoter read. A different one than in force is a 409:
    # they accepted a text that has since changed.
    version: str = Field(min_length=1, max_length=20)
