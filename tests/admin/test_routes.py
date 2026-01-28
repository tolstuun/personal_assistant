"""
Tests for Admin UI routes.

Tests verify route configuration and response handling.
"""

from fastapi.testclient import TestClient

from src.admin.app import create_admin_app


class TestAdminApp:
    """Tests for admin app configuration."""

    def test_create_admin_app_returns_fastapi(self) -> None:
        """create_admin_app returns a FastAPI instance."""
        from fastapi import FastAPI

        app = create_admin_app()
        assert isinstance(app, FastAPI)

    def test_admin_app_has_routes(self) -> None:
        """Admin app has expected routes configured."""
        app = create_admin_app()
        routes = [route.path for route in app.routes]

        # Auth routes
        assert "/login" in routes
        assert "/logout" in routes

        # Dashboard
        assert "/" in routes

        # Categories
        assert "/categories" in routes
        assert "/categories/new" in routes
        assert "/categories/{category_id}/edit" in routes

        # Sources
        assert "/sources" in routes
        assert "/sources/new" in routes
        assert "/sources/{source_id}/edit" in routes


class TestAuthRoutes:
    """Tests for authentication routes."""

    def test_login_page_accessible(self) -> None:
        """Login page is accessible without auth."""
        app = create_admin_app()
        client = TestClient(app)

        response = client.get("/login")
        assert response.status_code == 200
        assert "Password" in response.text

    def test_login_page_has_form(self) -> None:
        """Login page contains a form."""
        app = create_admin_app()
        client = TestClient(app)

        response = client.get("/login")
        assert '<form' in response.text
        assert 'type="password"' in response.text

    def test_logout_redirects_to_login(self) -> None:
        """Logout redirects to login page."""
        app = create_admin_app()
        client = TestClient(app, follow_redirects=False)

        response = client.get("/logout")
        assert response.status_code == 303
        assert response.headers["location"] == "/admin/login"


class TestProtectedRoutes:
    """Tests for protected routes requiring authentication."""

    def test_dashboard_redirects_without_auth(self) -> None:
        """Dashboard redirects to login without auth."""
        app = create_admin_app()
        client = TestClient(app, follow_redirects=False)

        response = client.get("/")
        assert response.status_code == 303
        assert "/login" in response.headers["location"]

    def test_categories_redirects_without_auth(self) -> None:
        """Categories page redirects to login without auth."""
        app = create_admin_app()
        client = TestClient(app, follow_redirects=False)

        response = client.get("/categories")
        assert response.status_code == 303

    def test_sources_redirects_without_auth(self) -> None:
        """Sources page redirects to login without auth."""
        app = create_admin_app()
        client = TestClient(app, follow_redirects=False)

        response = client.get("/sources")
        assert response.status_code == 303
