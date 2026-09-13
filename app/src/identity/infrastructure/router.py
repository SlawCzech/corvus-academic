"""FastAPI router — aggregates the identity endpoints into one router.

Every endpoint lives in its own module by resource (``auth_router.py`` /
``users_router.py`` / ``settings_router.py`` / ``admin_router.py``); this is
only the seam ``main.py`` imports.

NOTE: the former ``/internal/users/{user_id}`` and
``/internal/token/introspect`` endpoints were removed during the
gateway/identity/parser consolidation. Their only protection was network
topology — gateway did not proxy them and identity listened on an internal
port. Now that this router is mounted on the public port, they would have
exposed an unauthenticated user lookup and a public token oracle. Nothing
called them (agent verifies JWT locally with the shared secret), so they
were deleted rather than given real auth.
"""

from fastapi import APIRouter

from src.identity.infrastructure.admin_router import router as admin_router
from src.identity.infrastructure.auth_router import router as auth_router
from src.identity.infrastructure.settings_router import router as settings_router
from src.identity.infrastructure.users_router import router as users_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(users_router)
router.include_router(settings_router)
router.include_router(admin_router)
