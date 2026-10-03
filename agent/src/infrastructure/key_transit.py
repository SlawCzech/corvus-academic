"""Seal a promoter's provider key for its trip through the Celery broker.

The key is a task argument, and a task message sits in Redis for the whole
run: with late acks it stays there, unacknowledged, until the worker is done
(up to the two-hour visibility timeout). Anyone who can read Redis — a
`MONITOR`, an RDB snapshot on disk, Flower's task view — would read the key.
Sealed, they read a Fernet token.

The API process seals, the worker unseals, and both are this service: the
Fernet key is derived from the ``JWT_SECRET`` they already share, with HKDF
and a purpose label, so it is not the JWT key itself and the deployment needs
no new secret. Rotating ``JWT_SECRET`` makes a task queued before the rotation
fail to unseal — it fails with that reason, it does not run keyless.

See ADR 0012.
"""

import base64
from functools import cache

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from src.infrastructure.settings import settings

_PURPOSE = b"corvus agent: provider key in the task queue"


class KeyUnsealError(ValueError):
    """A sealed key that this service cannot open."""


@cache
def _fernet(secret: str) -> Fernet:
    derived = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None, info=_PURPOSE
    ).derive(secret.encode())
    return Fernet(base64.urlsafe_b64encode(derived))


def seal(api_key: str) -> str:
    """Encrypt a key for a task argument."""
    return _fernet(settings.jwt_secret).encrypt(api_key.encode()).decode()


def unseal(token: str) -> str:
    """Decrypt a key sealed by :func:`seal`, in the worker that will use it."""
    try:
        return _fernet(settings.jwt_secret).decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise KeyUnsealError(
            "The provider key could not be decrypted — was JWT_SECRET changed "
            "while the action waited in the queue?"
        ) from exc
