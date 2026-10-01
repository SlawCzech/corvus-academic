"""Asking the provider whether a key works, before it is stored.

Without this a mistyped key surfaced only on the promoter's next AI action,
minutes later, as a failed run. The question is the cheapest one the
provider answers — which models does this key see — and costs nothing.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class KeyVerdict(StrEnum):
    """What the provider said about a key."""

    ACCEPTED = "accepted"
    # Refused: revoked, mistyped, from another account type — or a key the
    # provider knows but will not serve as sent (one not scoped to a
    # workspace, say). Either way an action run on it would fail the same way.
    REJECTED = "rejected"
    # No answer worth trusting — offline, provider down, rate limited. The
    # key is stored anyway: a local deployment without internet should not
    # lose the ability to save one.
    UNCHECKED = "unchecked"


@dataclass(frozen=True)
class KeyCheck:
    """The verdict, and for a refusal the provider's own words for it.

    "Rejected" alone sends the promoter looking for a typo; the provider
    usually says exactly what is wrong.
    """

    verdict: KeyVerdict
    provider_message: str | None = None


class KeyChecker(Protocol):
    """Asks a provider whether a key is valid."""

    async def check(self, provider: str, api_key: str) -> KeyCheck: ...
