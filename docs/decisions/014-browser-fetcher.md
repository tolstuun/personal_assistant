# 014: Playwright Browser Fetcher

## Status
Accepted

## Problem
Some security news websites block simple HTTP requests (returning 403 or 429) because they detect non-browser user-agents or require JavaScript rendering. This causes the content fetcher to miss articles from these sources entirely.

## Solution

### BrowserFetcher (`src/core/primitives/fetchers/browser.py`)
A module that uses Playwright to fetch pages with a headless Chromium browser:

- Launches browser once (lazy init), reuses across fetches
- Creates a fresh browser context per fetch (isolates cookies/state)
- Mimics real user: realistic user-agent, 1920x1080 viewport, random delay
- Returns raw HTML string (not articles — that's WebsiteFetcher's job)

### Integration with WebsiteFetcher
WebsiteFetcher gets a new `_fetch_with_fallback(url)` method:

1. Check domain cache — if cached, go straight to Playwright
2. Try HTTP (existing Fetcher primitive)
3. If 403/429, add domain to cache, retry with Playwright
4. Playwright failure — return None (same as current HTTP failure)

### Domain Cache
- In-memory set on the WebsiteFetcher instance
- Tracks domains that returned 403/429
- Resets on application restart (intentional — no persistence needed)
- Prevents wasting time retrying HTTP for known-blocked domains

### Setting: `browser_fetcher_enabled`
- Type: boolean, default: true
- When disabled, WebsiteFetcher works exactly as before (HTTP only)
- Configurable via Admin UI Settings page

### Why not a separate BaseFetcher?
BrowserFetcher is not a source type — it's a transport mechanism. WebsiteFetcher still handles link extraction, content parsing, and article creation. The browser is just an alternative way to get the HTML.

## Dependencies
- `playwright>=1.40.0` in pyproject.toml
- `playwright install chromium` required at deployment

## How to Test

```bash
# Unit tests (mocked Playwright, no browser needed)
pytest tests/core/primitives/fetchers/test_browser.py -v
pytest tests/core/primitives/fetchers/test_website.py -v

# Verify setting exists
pytest tests/core/services/test_settings.py -v
```
