"""
Tests for browser-based page fetcher (Playwright).

All tests mock Playwright to avoid needing a real browser.
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.core.primitives.fetchers import browser

PATCH_PW = "src.core.primitives.fetchers.browser.async_playwright"
PATCH_SLEEP = "src.core.primitives.fetchers.browser.asyncio.sleep"


@pytest.fixture(autouse=True)
def _reset_browser_globals():
    """Reset module-level globals before each test."""
    browser._playwright = None
    browser._browser = None
    yield
    browser._playwright = None
    browser._browser = None


def _make_mock_playwright():
    """Create a full chain of mocked Playwright objects.

    Returns:
        Tuple of (playwright_cm, playwright, browser_instance, page).
    """
    page = AsyncMock()
    page.content.return_value = "<html><body>Hello</body></html>"

    context = AsyncMock()
    context.new_page.return_value = page

    browser_instance = AsyncMock()
    browser_instance.new_context.return_value = context

    playwright_obj = AsyncMock()
    playwright_obj.chromium.launch.return_value = browser_instance

    playwright_cm = AsyncMock()
    playwright_cm.start.return_value = playwright_obj

    return playwright_cm, playwright_obj, browser_instance, page


class TestBrowserStartup:
    """Tests for browser startup/shutdown lifecycle."""

    @pytest.mark.asyncio
    async def test_startup_creates_browser(self) -> None:
        """startup() launches a Chromium browser."""
        pw_cm, pw_obj, br_inst, _ = _make_mock_playwright()

        with patch(PATCH_PW, return_value=pw_cm):
            await browser.startup()

        assert browser._browser is br_inst
        assert browser._playwright is pw_obj
        pw_obj.chromium.launch.assert_called_once()

    @pytest.mark.asyncio
    async def test_startup_is_idempotent(self) -> None:
        """Calling startup() twice does not launch two browsers."""
        pw_cm, pw_obj, _, _ = _make_mock_playwright()

        with patch(PATCH_PW, return_value=pw_cm):
            await browser.startup()
            await browser.startup()

        pw_obj.chromium.launch.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_closes_browser(self) -> None:
        """shutdown() closes the browser and playwright."""
        mock_browser = AsyncMock()
        mock_playwright = AsyncMock()
        browser._browser = mock_browser
        browser._playwright = mock_playwright

        await browser.shutdown()

        mock_browser.close.assert_called_once()
        mock_playwright.stop.assert_called_once()
        assert browser._browser is None
        assert browser._playwright is None

    @pytest.mark.asyncio
    async def test_shutdown_when_not_started(self) -> None:
        """shutdown() is safe when browser was never started."""
        await browser.shutdown()
        assert browser._browser is None
        assert browser._playwright is None


class TestBrowserFetchPage:
    """Tests for the fetch_page function."""

    @pytest.mark.asyncio
    async def test_fetch_page_success(self) -> None:
        """Successful page fetch returns HTML."""
        pw_cm, _, _, page = _make_mock_playwright()

        with patch(PATCH_PW, return_value=pw_cm):
            with patch(PATCH_SLEEP, new_callable=AsyncMock):
                result = await browser.fetch_page(
                    "https://example.com",
                )

        assert result == "<html><body>Hello</body></html>"
        page.goto.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_page_returns_none_on_error(self) -> None:
        """Returns None when page load raises an exception."""
        pw_cm, _, _, page = _make_mock_playwright()
        page.goto.side_effect = RuntimeError("Navigation failed")

        with patch(PATCH_PW, return_value=pw_cm):
            result = await browser.fetch_page(
                "https://example.com",
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_page_returns_none_on_timeout(self) -> None:
        """Returns None on timeout."""
        pw_cm, _, _, page = _make_mock_playwright()
        page.goto.side_effect = TimeoutError("Timed out")

        with patch(PATCH_PW, return_value=pw_cm):
            result = await browser.fetch_page(
                "https://example.com",
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_page_auto_starts_browser(self) -> None:
        """fetch_page() calls startup() if browser is None."""
        pw_cm, _, _, _ = _make_mock_playwright()

        with patch(PATCH_PW, return_value=pw_cm):
            with patch(PATCH_SLEEP, new_callable=AsyncMock):
                result = await browser.fetch_page(
                    "https://example.com",
                )

        assert browser._browser is not None
        assert result is not None

    @pytest.mark.asyncio
    async def test_context_is_closed_after_fetch(self) -> None:
        """Browser context is closed after fetch."""
        pw_cm, _, br_inst, _ = _make_mock_playwright()
        context = br_inst.new_context.return_value

        with patch(PATCH_PW, return_value=pw_cm):
            with patch(PATCH_SLEEP, new_callable=AsyncMock):
                await browser.fetch_page("https://example.com")

        context.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_is_closed_on_error(self) -> None:
        """Browser context is closed even when page load fails."""
        pw_cm, _, br_inst, page = _make_mock_playwright()
        page.goto.side_effect = RuntimeError("Navigation failed")
        context = br_inst.new_context.return_value

        with patch(PATCH_PW, return_value=pw_cm):
            await browser.fetch_page("https://example.com")

        context.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_page_passes_timeout(self) -> None:
        """fetch_page passes timeout_ms to page.goto."""
        pw_cm, _, _, page = _make_mock_playwright()

        with patch(PATCH_PW, return_value=pw_cm):
            with patch(PATCH_SLEEP, new_callable=AsyncMock):
                await browser.fetch_page(
                    "https://example.com",
                    timeout_ms=15000,
                )

        call_kwargs = page.goto.call_args.kwargs
        assert call_kwargs["timeout"] == 15000

    @pytest.mark.asyncio
    async def test_fetch_page_default_timeout_is_60s(self) -> None:
        """Default timeout is 60000ms (60 seconds)."""
        pw_cm, _, _, page = _make_mock_playwright()

        with patch(PATCH_PW, return_value=pw_cm):
            with patch(PATCH_SLEEP, new_callable=AsyncMock):
                await browser.fetch_page("https://example.com")

        call_kwargs = page.goto.call_args.kwargs
        assert call_kwargs["timeout"] == 60000

    @pytest.mark.asyncio
    async def test_fetch_page_uses_domcontentloaded(self) -> None:
        """fetch_page uses domcontentloaded wait strategy."""
        pw_cm, _, _, page = _make_mock_playwright()

        with patch(PATCH_PW, return_value=pw_cm):
            with patch(PATCH_SLEEP, new_callable=AsyncMock):
                await browser.fetch_page("https://example.com")

        call_kwargs = page.goto.call_args.kwargs
        assert call_kwargs["wait_until"] == "domcontentloaded"

    @pytest.mark.asyncio
    async def test_fetch_page_fallback_to_commit(self) -> None:
        """Falls back to 'commit' when domcontentloaded times out."""
        pw_cm, _, _, page = _make_mock_playwright()
        # First call (domcontentloaded) times out, second (commit) succeeds
        page.goto.side_effect = [TimeoutError("Timed out"), None]

        with patch(PATCH_PW, return_value=pw_cm):
            with patch(PATCH_SLEEP, new_callable=AsyncMock):
                result = await browser.fetch_page(
                    "https://example.com",
                )

        assert result == "<html><body>Hello</body></html>"
        assert page.goto.call_count == 2
        first_call = page.goto.call_args_list[0]
        assert first_call.kwargs["wait_until"] == "domcontentloaded"
        second_call = page.goto.call_args_list[1]
        assert second_call.kwargs["wait_until"] == "commit"

    @pytest.mark.asyncio
    async def test_fetch_page_commit_fallback_also_fails(self) -> None:
        """Returns None when both strategies fail."""
        pw_cm, _, _, page = _make_mock_playwright()
        page.goto.side_effect = [
            TimeoutError("domcontentloaded timeout"),
            TimeoutError("commit timeout"),
        ]

        with patch(PATCH_PW, return_value=pw_cm):
            result = await browser.fetch_page(
                "https://example.com",
            )

        assert result is None
        assert page.goto.call_count == 2
