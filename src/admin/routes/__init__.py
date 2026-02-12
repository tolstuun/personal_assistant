"""Admin routes package."""

from src.admin.routes.auth import router as auth_router
from src.admin.routes.categories import router as categories_router
from src.admin.routes.dashboard import router as dashboard_router
from src.admin.routes.digests import router as digests_router
from src.admin.routes.operations import router as operations_router
from src.admin.routes.settings import router as settings_router
from src.admin.routes.sources import router as sources_router

__all__ = [
    "auth_router",
    "dashboard_router",
    "categories_router",
    "digests_router",
    "operations_router",
    "sources_router",
    "settings_router",
]
