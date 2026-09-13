"""Dashboard summary endpoint — stats and recent activity across a promoter's students.

A separate top-level prefix rather than nesting under ``/students/{id}``,
so it can never collide with that path-param route.
"""

from fastapi import APIRouter

from src.mentoring.infrastructure.dependencies import CallerDep, DashboardServiceDep
from src.mentoring.infrastructure.schemas import (
    DashboardSummaryResponse,
    dashboard_summary_response,
)

router = APIRouter(prefix="/dashboard", tags=["mentoring"])


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    caller: CallerDep,
    svc: DashboardServiceDep,
) -> DashboardSummaryResponse:
    """Return the caller's at-a-glance dashboard summary."""
    summary = await svc.summary(caller)
    return dashboard_summary_response(summary)
