"""Exceptions raised by mentoring's application services.

One file so a caller — an endpoint, a test — needs exactly one import to
catch or assert on anything this bounded context's use cases can raise,
instead of knowing which of five modules happened to define which error.

Framework-free on purpose: these are business outcomes, not HTTP status
codes. Mapping them onto ``HTTPException`` happens once, in
``infrastructure/errors.py`` — this module has no FastAPI import and never
should.
"""


class StudentNotFoundError(Exception):
    """Raised when a student does not exist *or* is not visible to the caller.

    One error for both cases on purpose: a promoter asking for someone else's
    student learns nothing about whether that id exists.
    """


class DraftNotFoundError(Exception):
    """Raised when a draft, or its file, does not exist for this student."""


class ActionNotFoundError(Exception):
    """Raised when an action does not exist, or belongs to another student."""


class UnsupportedActionError(Exception):
    """Raised for an action type `app` cannot assemble a context for."""


class MissingContextError(Exception):
    """The student's record does not yet hold what this action needs.

    Raised before anything is dispatched — asking for defence questions
    without a thesis, or for a progress check with only one version, is a
    state problem, not a model problem.
    """


class AgentUnavailableError(Exception):
    """The agent service could not be reached, or refused the request."""
