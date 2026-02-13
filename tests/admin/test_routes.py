"""
Tests for Admin UI routes.

Tests verify route configuration and response handling.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from src.admin.app import create_admin_app
from src.admin.auth import require_auth


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
        assert "<form" in response.text
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

    def test_settings_redirects_without_auth(self) -> None:
        """Settings page redirects to login without auth."""
        app = create_admin_app()
        client = TestClient(app, follow_redirects=False)

        response = client.get("/settings")
        assert response.status_code == 303


class TestSettingsRoutes:
    """Tests for settings routes."""

    def test_settings_route_exists(self) -> None:
        """Settings route is configured."""
        app = create_admin_app()
        routes = [route.path for route in app.routes]

        assert "/settings" in routes

    def test_settings_update_route_exists(self) -> None:
        """Settings update route is configured."""
        app = create_admin_app()
        routes = [route.path for route in app.routes]

        assert "/settings/{key}" in routes


class TestOperationsRoutes:
    """Tests for operations routes."""

    def test_operations_route_exists(self) -> None:
        """Operations route is configured."""
        app = create_admin_app()
        routes = [route.path for route in app.routes]

        assert "/operations" in routes

    def test_operations_redirects_without_auth(self) -> None:
        """Operations page redirects to login without auth."""
        app = create_admin_app()
        client = TestClient(app, follow_redirects=False)

        response = client.get("/operations")
        assert response.status_code == 303


class TestOperationsDigestStatus:
    """Tests for digest status panel on operations page."""

    def test_operations_template_has_digest_status_heading(self) -> None:
        """Operations template includes a Digest Status section heading."""
        from pathlib import Path

        template_path = Path("src/admin/templates/operations.html")
        content = template_path.read_text()
        assert "Digest Status" in content


def _mock_session_factory(query_results: dict | None = None) -> MagicMock:
    """
    Create a mock async DB session that returns controlled query results.

    Args:
        query_results: Map of table name to list of scalars to return.
    """
    results = query_results or {}

    async def mock_execute(stmt):
        result_mock = MagicMock()
        # Determine which query this is by inspecting the statement string
        stmt_str = str(stmt)
        if "job_runs" in stmt_str and "fetch_cycle" in stmt_str:
            result_mock.scalar_one_or_none.return_value = results.get("latest_fetch")
        elif "job_runs" in stmt_str and "digest_scheduler" in stmt_str:
            result_mock.scalar_one_or_none.return_value = results.get("latest_scheduler")
        elif "digests" in stmt_str:
            result_mock.scalar_one_or_none.return_value = results.get("latest_digest")
        elif "articles" in stmt_str and "count" in stmt_str.lower():
            result_mock.scalar_one.return_value = results.get("article_count", 0)
        elif "job_runs" in stmt_str:
            scalars_mock = MagicMock()
            scalars_mock.all.return_value = results.get("recent_runs", [])
            result_mock.scalars.return_value = scalars_mock
        else:
            result_mock.scalar_one_or_none.return_value = None
        return result_mock

    session = MagicMock()
    session.execute = mock_execute
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    db = MagicMock()
    db.session.return_value = session
    return db


class TestOperationsAuthenticated:
    """Tests for operations page with mocked auth and DB."""

    def _make_client(self, query_results: dict | None = None) -> TestClient:
        """Create a test client with mocked auth, DB, and settings."""
        app = create_admin_app()
        app.dependency_overrides[require_auth] = lambda: True

        mock_db = _mock_session_factory(query_results)

        self._patches = [
            # Bypass middleware auth check
            patch("src.admin.app.get_auth_status", return_value=True),
            patch("src.admin.routes.operations.get_db", new_callable=AsyncMock, return_value=mock_db),
            patch("src.admin.routes.operations.SettingsService"),
        ]
        for p in self._patches:
            mock = p.start()
            if hasattr(p, "attribute") and p.attribute == "SettingsService":
                instance = mock.return_value
                async def mock_get(key: str) -> object:
                    return {"digest_time": "08:00", "telegram_notifications": True}[key]
                instance.get = AsyncMock(side_effect=mock_get)

        return TestClient(app)

    def _cleanup(self) -> None:
        for p in self._patches:
            p.stop()

    def test_operations_returns_200_no_data(self) -> None:
        """Operations page returns 200 with empty DB (no digests, no runs)."""
        client = self._make_client()
        try:
            response = client.get("/operations")
            assert response.status_code == 200
            assert "Operations" in response.text
            assert "Digest Status" in response.text
        finally:
            self._cleanup()

    def test_operations_returns_200_with_digest(self) -> None:
        """Operations page returns 200 when a digest exists (no lazy-load)."""
        digest = MagicMock()
        digest.date = datetime(2026, 2, 12).date()
        digest.id = "test-digest-id"
        digest.created_at = datetime(2026, 2, 12, 8, 5, 0)
        digest.notified_at = datetime(2026, 2, 12, 8, 5, 30)

        client = self._make_client({
            "latest_digest": digest,
            "article_count": 5,
        })
        try:
            response = client.get("/operations")
            assert response.status_code == 200
            assert "Digest Status" in response.text
        finally:
            self._cleanup()
