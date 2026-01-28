"""
Admin Web UI FastAPI application.

Provides HTMX-based interface for managing Security Digest
categories and sources. Mounted at /admin on the main app.
"""

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.admin.auth import get_auth_status
from src.admin.routes import (
    auth_router,
    categories_router,
    dashboard_router,
    sources_router,
)


class AuthRedirectMiddleware(BaseHTTPMiddleware):
    """Middleware to redirect unauthenticated requests to login."""

    async def dispatch(self, request: Request, call_next):
        """Check auth for protected routes."""
        path = request.url.path

        # Allow access to login/logout without auth
        # Check both mounted (/admin/login) and standalone (/login) paths
        public_paths = ["/login", "/logout", "/admin/login", "/admin/logout"]
        if any(path.endswith(p) for p in public_paths):
            return await call_next(request)

        # Check authentication
        if not get_auth_status(request):
            # Determine correct redirect URL based on mount point
            if path.startswith("/admin"):
                return RedirectResponse(url="/admin/login", status_code=303)
            return RedirectResponse(url="/login", status_code=303)

        return await call_next(request)


def create_admin_app() -> FastAPI:
    """
    Create and configure the admin FastAPI application.

    Returns:
        Configured FastAPI app for admin UI.
    """
    admin_app = FastAPI(
        title="Security Digest Admin",
        docs_url=None,  # Disable Swagger for admin
        redoc_url=None,
    )

    # Add auth middleware
    admin_app.add_middleware(AuthRedirectMiddleware)

    # Include routers
    admin_app.include_router(auth_router)
    admin_app.include_router(dashboard_router)
    admin_app.include_router(categories_router)
    admin_app.include_router(sources_router)

    return admin_app


# Create app instance for mounting
admin_app = create_admin_app()
