"""FastAPI router — aggregates the mentoring endpoints into one router.

Every endpoint lives in its own module by resource
(``students_router.py`` / ``actions_router.py`` / ``drafts_router.py``);
this is only the seam ``main.py`` imports, so splitting those files further
never touches the one line that wires this bounded context into the app.
"""

from fastapi import APIRouter

from src.mentoring.infrastructure.actions_router import router as actions_router
from src.mentoring.infrastructure.dashboard_router import router as dashboard_router
from src.mentoring.infrastructure.drafts_router import router as drafts_router
from src.mentoring.infrastructure.fragments_router import router as fragments_router
from src.mentoring.infrastructure.models_router import router as models_router
from src.mentoring.infrastructure.students_router import router as students_router

router = APIRouter()
router.include_router(students_router)
router.include_router(actions_router)
router.include_router(drafts_router)
router.include_router(fragments_router)
router.include_router(dashboard_router)
router.include_router(models_router)
