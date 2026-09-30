"""Asking the provider whether a key works, before it is stored.

Without this a mistyped key surfaced only on the promoter's next AI action,
minutes later, as a failed run. The question is the cheapest one the
provider answers — which models does this key see — and costs nothing.
"""

from enum import StrEnum
from typing import Protocol


class KeyVerdict(StrEnum):
    """What the provider said about a key."""

    ACCEPTED = "accepted"
    # Refused outright: revoked, mistyped, or from another account type.
    REJECTED = "rejected"
    # No answer worth trusting — offline, provider down, rate limited. The
    # key is stored anyway: a local deployment without internet should not
    # lose the ability to save one.
    UNCHECKED = "unchecked"


class KeyChecker(Protocol):
    """Asks a provider whether a key is valid."""

    async def check(self, provider: str, api_key: str) -> KeyVerdict: ...
