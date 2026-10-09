"""AI action endpoints — trigger, poll, and accept."""

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, HTTPException, Query, status

from src.mentoring.application.exceptions import (
    ActionNotFoundError,
    AgentUnavailableError,
    MissingContextError,
    ProviderKeyMissingError,
    ProviderRequiredError,
    StudentNotFoundError,
    UnsupportedActionError,
)
from src.mentoring.domain.action import ActionType
from src.mentoring.domain.model_policy import ModelNotAllowedError
from src.mentoring.infrastructure.dependencies import (
    ActionServiceDep,
    CallerDep,
    KeyLoaderDep,
    TokenDep,
)
from src.mentoring.infrastructure.errors import not_found
from src.mentoring.infrastructure.schemas import (
    ActionAcceptRequest,
    ActionResponse,
    ActionResumeRequest,
    ActionTriggerRequest,
    action_response,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter(prefix="/students", tags=["mentoring"])


def _no_key(exc: ProviderKeyMissingError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"No API key stored for provider {exc}",
    )


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
    keys: KeyLoaderDep,
    svc: ActionServiceDep,
) -> ActionResponse:
    """Run one AI action for a student and return the queued action record.

    Returns immediately: the work happens in the agent's Celery worker, and
    the caller polls the action's own endpoint for the outcome. The run goes
    on the provider the promoter picked, with their own key for it, or — with
    no provider — on the self-hosted model, where the server offers one.
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
            review_tone=body.review_tone,
            provider=body.provider,
            keys=keys,
            review_findings_first=body.review_findings_first,
        )
    except StudentNotFoundError as exc:
        raise not_found(exc) from exc
    except UnsupportedActionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except ModelNotAllowedError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except ProviderKeyMissingError as exc:
        # Asked to run on a provider there is no stored key for.
        raise _no_key(exc) from exc
    except ProviderRequiredError as exc:
        # No provider picked, and this server runs no local models.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This server runs no local models — pick a provider "
            "you have an API key for",
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
    token: TokenDep,
    svc: ActionServiceDep,
    action_type: Annotated[ActionType | None, Query(alias="type")] = None,
) -> list[ActionResponse]:
    """Return a student's AI action history, newest first, unfinished ones refreshed."""
    try:
        actions = await svc.list_actions(caller, student_id, token, action_type)
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


@router.post("/{student_id}/actions/{action_id}/resume", response_model=ActionResponse)
async def resume_action(
    student_id: uuid.UUID,
    action_id: uuid.UUID,
    body: ActionResumeRequest,
    caller: CallerDep,
    token: TokenDep,
    keys: KeyLoaderDep,
    svc: ActionServiceDep,
) -> ActionResponse:
    """Write the paused review from the findings the promoter kept."""
    try:
        action = await svc.resume(
            caller,
            student_id,
            action_id,
            accepted_findings=body.accepted_findings,
            token=token,
            keys=keys,
        )
    except (StudentNotFoundError, ActionNotFoundError) as exc:
        raise not_found(exc) from exc
    except ProviderKeyMissingError as exc:
        # The key the review started on has been removed since.
        raise _no_key(exc) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except AgentUnavailableError as exc:
        # Still paused on the agent's side; the promoter can try again.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The analysis service is unavailable",
        ) from exc
    return action_response(action)


@router.post("/{student_id}/actions/{action_id}/cancel", response_model=ActionResponse)
async def cancel_action(
    student_id: uuid.UUID,
    action_id: uuid.UUID,
    caller: CallerDep,
    token: TokenDep,
    svc: ActionServiceDep,
) -> ActionResponse:
    """Stop an action that has not finished — a mistake, or a run long dead."""
    try:
        action = await svc.cancel(caller, student_id, action_id, token)
    except (StudentNotFoundError, ActionNotFoundError) as exc:
        raise not_found(exc) from exc
    except ValueError as exc:
        # Already completed, failed or cancelled.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return action_response(action)


@router.delete(
    "/{student_id}/actions/{action_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_action(
    student_id: uuid.UUID,
    action_id: uuid.UUID,
    caller: CallerDep,
    token: TokenDep,
    svc: ActionServiceDep,
) -> None:
    """Delete an action from the history, result and all — a running one too."""
    try:
        await svc.delete(caller, student_id, action_id, token)
    except (StudentNotFoundError, ActionNotFoundError) as exc:
        raise not_found(exc) from exc
    except AgentUnavailableError as exc:
        # Nothing was deleted; the agent's side is idempotent, so retry.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The analysis service is unavailable",
        ) from exc
