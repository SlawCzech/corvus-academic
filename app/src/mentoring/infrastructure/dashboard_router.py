"""Dashboard summary endpoint — stats and recent activity across a promoter's students.

A separate top-level prefix rather than nesting under ``/students/{id}``,
so it can never collide with that path-param route.
"""

from fastapi import APIRouter

from src.mentoring.infrastructure.dependencies import (
    ActionServiceDep,
    CallerDep,
    DashboardServiceDep,
    TokenDep,
)
from src.mentoring.infrastructure.schemas import (
    ActionInProgressResponse,
    DashboardSummaryResponse,
    action_in_progress_response,
    dashboard_summary_response,
)

router = APIRouter(prefix="/dashboard", tags=["mentoring"])


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    caller: CallerDep,
    token: TokenDep,
    svc: DashboardServiceDep,
) -> DashboardSummaryResponse:
    """Return the caller's at-a-glance dashboard summary."""
    summary = await svc.summary(caller, token)
    return dashboard_summary_response(summary)


@router.get("/actions-in-progress", response_model=list[ActionInProgressResponse])
async def list_actions_in_progress(
    caller: CallerDep,
    token: TokenDep,
    svc: ActionServiceDep,
) -> list[ActionInProgressResponse]:
    """What the "in progress" count is made of: oldest first, checked with agent."""
    return [
        action_in_progress_response(a) for a in await svc.in_progress(caller, token)
    ]
