"""
Browser-based page fetcher using Playwright.

Used as a fallback when standard HTTP requests get blocked (403/429).
Launches a headless Chromium browser that renders JavaScript and
mimics a real user to bypass bot detection.
"""

import asyncio
import logging
import random

from playwright.async_api import Browser, Playwright, async_playwright

logger = logging.getLogger(__name__)

# Module-level singleton
_playwright: Playwright | None = None
_browser: Browser | None = None


async def startup() -> None:
    """
    Launch the Playwright browser.

    Call this once at application startup or let fetch_page()
    call it lazily on first use. The browser process is reused
    for all page fetches to avoid repeated launch overhead.
    """
    global _playwright, _browser
    if _browser is not None:
        return

    _playwright = await async_playwright().start()
    _browser = await _playwright.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ],
    )
    logger.info("Playwright browser launched")


async def shutdown() -> None:
    """
    Close the Playwright browser and clean up resources.

    Call this at application shutdown.
    """
    global _playwright, _browser
    if _browser is not None:
        await _browser.close()
        _browser = None
    if _playwright is not None:
        await _playwright.stop()
        _playwright = None
    logger.info("Playwright browser closed")


async def fetch_page(url: str, timeout_ms: int = 30000) -> str | None:
    """
    Fetch a page using a headless browser and return its HTML.

    Creates a fresh browser context for each request to isolate
    cookies and state. Mimics a real user with realistic user-agent,
    viewport, and a small random delay after page load.

    Args:
        url: The URL to fetch.
        timeout_ms: Maximum time to wait for page load in milliseconds.

    Returns:
        The page HTML content, or None if the fetch failed.
    """
    global _browser

    if _browser is None:
        await startup()

    if _browser is None:
        logger.error("Failed to start Playwright browser")
        return None

    context = None
    try:
        context = await _browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            java_script_enabled=True,
        )

        page = await context.new_page()
        await page.goto(url, wait_until="networkidle", timeout=timeout_ms)

        # Small random delay to let JS-rendered content settle
        await asyncio.sleep(random.uniform(1.0, 3.0))

        html = await page.content()
        logger.info(f"Browser fetched {url} ({len(html)} bytes)")
        return html

    except Exception as e:
        logger.warning(f"Browser fetch failed for {url}: {e}")
        return None

    finally:
        if context is not None:
            await context.close()
