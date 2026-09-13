"""AI action endpoints — trigger, poll, and accept."""

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, HTTPException, Query, status

from src.mentoring.application.exceptions import (
    ActionNotFoundError,
    AgentUnavailableError,
    MissingContextError,
    StudentNotFoundError,
    UnsupportedActionError,
)
from src.mentoring.domain.action import ActionType
from src.mentoring.infrastructure.dependencies import (
    ActionServiceDep,
    BYOKDep,
    CallerDep,
    TokenDep,
)
from src.mentoring.infrastructure.errors import not_found
from src.mentoring.infrastructure.schemas import (
    ActionAcceptRequest,
    ActionResponse,
    ActionTriggerRequest,
    action_response,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter(prefix="/students", tags=["mentoring"])


@router.post(
    "/{student_id}/actions",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_action(
    student_id: uuid.UUID,
    body: ActionTriggerRequest,
    caller: CallerDep,
    token: TokenDep,
    byok: BYOKDep,
    svc: ActionServiceDep,
) -> ActionResponse:
    """Run one AI action for a student and return the queued action record.

    Returns immediately: the work happens in the agent's Celery worker, and
    the caller polls the action's own endpoint for the outcome. When the
    promoter has stored their own provider key, the run goes on their
    account; otherwise it goes to the self-hosted model.
    """
    try:
        action = await svc.trigger(
            caller,
            student_id,
            action_type=body.action_type,
            token=token,
            detail=body.detail,
            model=body.model,
            language=body.language,
            byok=byok,
        )
    except StudentNotFoundError as exc:
        raise not_found(exc) from exc
    except UnsupportedActionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except MissingContextError as exc:
        # The student's record does not hold what this action needs yet —
        # no draft uploaded, only one version, no rough notes to write up.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except AgentUnavailableError as exc:
        # The attempt is recorded as failed; the promoter can retry.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The analysis service is unavailable",
        ) from exc
    return action_response(action)


@router.get("/{student_id}/actions", response_model=list[ActionResponse])
async def list_actions(
    student_id: uuid.UUID,
    caller: CallerDep,
    svc: ActionServiceDep,
    action_type: Annotated[ActionType | None, Query(alias="type")] = None,
) -> list[ActionResponse]:
    """Return a student's AI action history, newest first."""
    try:
        actions = await svc.list_actions(caller, student_id, action_type)
    except StudentNotFoundError as exc:
        raise not_found(exc) from exc
    return [action_response(a) for a in actions]


@router.get("/{student_id}/actions/{action_id}", response_model=ActionResponse)
async def get_action(
    student_id: uuid.UUID,
    action_id: uuid.UUID,
    caller: CallerDep,
    token: TokenDep,
    svc: ActionServiceDep,
) -> ActionResponse:
    """Poll one action — refreshed from the agent while it is still running."""
    try:
        action = await svc.get_action(caller, student_id, action_id, token)
    except (StudentNotFoundError, ActionNotFoundError) as exc:
        raise not_found(exc) from exc
    return action_response(action)


@router.patch("/{student_id}/actions/{action_id}/accept", response_model=ActionResponse)
async def accept_action(
    student_id: uuid.UUID,
    action_id: uuid.UUID,
    body: ActionAcceptRequest,
    caller: CallerDep,
    svc: ActionServiceDep,
) -> ActionResponse:
    """Accept an action's result — for a topic proposal, this sets the topic."""
    try:
        action = await svc.accept(
            caller, student_id, action_id, topic_index=body.topic_index
        )
    except (StudentNotFoundError, ActionNotFoundError) as exc:
        raise not_found(exc) from exc
    except ValueError as exc:
        # Accepting twice, accepting something still running, or picking a
        # topic index the model never proposed.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return action_response(action)
