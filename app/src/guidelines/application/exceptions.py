"""Exceptions raised by the guideline catalog's application services.

Framework-free, like mentoring's: mapping them onto HTTP happens once, in
``infrastructure/router.py``.
"""


class GuidelineNotFoundError(Exception):
    """A university, set or version does not exist, or is not visible.

    Drafts are invisible to anyone who cannot manage the catalog — to them a
    draft is the same as nothing.
    """


class GuidelineConflictError(Exception):
    """The request clashes with what is already there (a duplicate name)."""


class ProviderKeyMissingError(Exception):
    """The admin asked for a provider they hold no key for (ADR 0024)."""


class DrafterUnavailableError(Exception):
    """The agent could not be reached, or refused to take the draft."""
