"""Mapping mentoring's application exceptions onto HTTP responses.

One function because there is one shape of problem every router in this
package needs to communicate the same way, rather than each building its own
``HTTPException``.
"""

from fastapi import HTTPException, status


def conflict(exc: Exception) -> HTTPException:
    """Map a request the record's present state rules out to 409."""
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


def not_found(exc: Exception) -> HTTPException:
    """Map an invisible-or-missing student (or one of its actions) to 404.

    Deliberately not 403: a promoter must not be able to probe whether some
    other promoter's student id exists.
    """
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail=f"Not found: {exc}"
    )
