"""Issuing a session: an access token in the body, a refresh token in a cookie."""

from fastapi import Response

from src.identity.application.auth import create_access_token, create_refresh_token
from src.identity.domain.user import User
from src.shared.settings import settings

REFRESH_COOKIE = "refresh_token"
REFRESH_TTL = settings.refresh_token_expire_days * 24 * 3600


def start_session(response: Response, user: User) -> str:
    """Set a new refresh cookie on ``response`` and return a new access token.

    Login, refresh and a password change all end here, so the cookie is set
    the same way each time.
    """
    refresh_token, _jti = create_refresh_token(user)
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=REFRESH_TTL,
        path="/auth/refresh",
    )
    return create_access_token(user)
