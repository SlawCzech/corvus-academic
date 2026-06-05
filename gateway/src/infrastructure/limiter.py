"""Shared SlowAPI rate-limiter instance."""

from slowapi import Limiter  # type: ignore[import-untyped]
from slowapi.util import get_remote_address  # type: ignore[import-untyped]

limiter: Limiter = Limiter(key_func=get_remote_address)
