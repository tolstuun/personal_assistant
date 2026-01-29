"""
Website fetcher using trafilatura for article extraction.

This fetcher:
1. Downloads the listing page
2. Finds article links in the HTML
3. Fetches each article page
4. Extracts title, content, and date using trafilatura
"""

import asyncio
import logging
from datetime import datetime
from urllib.parse import urljoin, urlparse

import trafilatura
from bs4 import BeautifulSoup

from src.core.primitives.fetcher import Fetcher, FetcherConfig
from src.core.primitives.fetchers.base import BaseFetcher, ExtractedArticle

logger = logging.getLogger(__name__)


class WebsiteFetcher(BaseFetcher):
    """
    Fetches articles from websites.

    Uses the existing Fetcher primitive for HTTP requests
    and trafilatura for content extraction.
    """

    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 2,
        concurrent_limit: int = 5,
    ):
        """
        Initialize the website fetcher.

        Args:
            timeout: HTTP request timeout in seconds.
            max_retries: Number of retries for failed requests.
            concurrent_limit: Max concurrent article fetches.
        """
        self.fetcher = Fetcher(
            FetcherConfig(
                timeout=timeout,
                max_retries=max_retries,
            )
        )
        self.concurrent_limit = concurrent_limit

    async def fetch_articles(
        self,
        source_url: str,
        max_articles: int = 20,
    ) -> list[ExtractedArticle]:
        """
        Fetch articles from a website.

        Args:
            source_url: The listing page URL (e.g., blog homepage).
            max_articles: Maximum number of articles to fetch.

        Returns:
            List of extracted articles.
        """
        logger.info(f"Fetching articles from {source_url}")

        # Step 1: Fetch the listing page
        try:
            result = await self.fetcher.fetch(source_url)
            if not result.ok:
                logger.error(f"Failed to fetch {source_url}: HTTP {result.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error fetching {source_url}: {e}")
            return []

        # Step 2: Extract article links
        links = self._extract_article_links(result.text or "", source_url)
        logger.info(f"Found {len(links)} article links on {source_url}")

        # Limit to max_articles
        links = links[:max_articles]

        # Step 3: Fetch each article concurrently
        semaphore = asyncio.Semaphore(self.concurrent_limit)

        async def fetch_with_semaphore(url: str) -> ExtractedArticle | None:
            async with semaphore:
                return await self._fetch_single_article(url, source_url)

        tasks = [fetch_with_semaphore(url) for url in links]
        results = await asyncio.gather(*tasks)

        # Filter out None results
        articles = [a for a in results if a is not None]
        logger.info(f"Successfully extracted {len(articles)} articles from {source_url}")

        return articles

    def _extract_article_links(self, html: str, base_url: str) -> list[str]:
        """
        Extract article links from a listing page.

        Looks for links in common content areas and filters out
        navigation, footer, and other non-article links.

        Args:
            html: The HTML content of the listing page.
            base_url: Base URL for resolving relative links.

        Returns:
            List of absolute article URLs.
        """
        soup = BeautifulSoup(html, "html.parser")
        base_domain = urlparse(base_url).netloc

        # Remove navigation, footer, sidebar, header elements
        for tag in soup.find_all(
            ["nav", "footer", "aside", "header", "script", "style", "noscript"]
        ):
            tag.decompose()

        # Also remove elements with common non-content class/id names
        for selector in [
            "[class*='nav']",
            "[class*='menu']",
            "[class*='footer']",
            "[class*='sidebar']",
            "[class*='header']",
            "[class*='comment']",
            "[class*='social']",
            "[class*='share']",
            "[class*='widget']",
            "[id*='nav']",
            "[id*='menu']",
            "[id*='footer']",
            "[id*='sidebar']",
            "[id*='header']",
        ]:
            for tag in soup.select(selector):
                tag.decompose()

        links: list[str] = []
        seen_urls: set[str] = set()

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]

            # Skip empty, javascript, and anchor links
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            # Convert to absolute URL
            absolute_url = urljoin(base_url, href)

            # Parse the URL
            parsed = urlparse(absolute_url)

            # Skip non-http URLs
            if parsed.scheme not in ("http", "https"):
                continue

            # Normalize URL (remove fragment)
            normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                normalized += f"?{parsed.query}"

            # Skip if already seen
            if normalized in seen_urls:
                continue
            seen_urls.add(normalized)

            # Skip common non-article patterns
            path_lower = parsed.path.lower()
            skip_patterns = [
                "/tag/",
                "/tags/",
                "/category/",
                "/categories/",
                "/author/",
                "/page/",
                "/search",
                "/login",
                "/register",
                "/signup",
                "/about",
                "/contact",
                "/privacy",
                "/terms",
                "/feed",
                "/rss",
                ".xml",
                ".pdf",
                ".jpg",
                ".png",
                ".gif",
            ]
            if any(pattern in path_lower for pattern in skip_patterns):
                continue

            # Skip very short paths (likely homepage links)
            if len(parsed.path.strip("/")) < 3:
                continue

            # Prefer internal links, but allow external if they look like articles
            is_internal = parsed.netloc == base_domain or parsed.netloc == ""
            if is_internal:
                links.append(normalized)
            elif self._looks_like_article_url(normalized):
                # External links that look like articles (e.g., linked news)
                links.append(normalized)

        return links

    def _looks_like_article_url(self, url: str) -> bool:
        """
        Check if a URL looks like an article.

        Args:
            url: The URL to check.

        Returns:
            True if the URL pattern suggests it's an article.
        """
        parsed = urlparse(url)
        path = parsed.path.lower()

        # Common article URL patterns
        article_patterns = [
            "/article/",
            "/post/",
            "/blog/",
            "/news/",
            "/story/",
            "/20",  # Year in URL like /2024/01/
        ]
        return any(pattern in path for pattern in article_patterns)

    async def _fetch_single_article(
        self,
        url: str,
        source_url: str,
    ) -> ExtractedArticle | None:
        """
        Fetch and extract content from a single article URL.

        Args:
            url: The article URL.
            source_url: The original source listing page.

        Returns:
            ExtractedArticle or None if extraction failed.
        """
        try:
            result = await self.fetcher.fetch(url)
            if not result.ok:
                logger.warning(f"Failed to fetch article {url}: HTTP {result.status_code}")
                return None

            html = result.text
            if not html:
                logger.warning(f"Empty response from {url}")
                return None

            # Use trafilatura to extract content
            extracted = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=False,
                include_images=False,
                include_links=False,
                output_format="txt",
            )

            if not extracted:
                logger.warning(f"Could not extract content from {url}")
                return None

            # Extract metadata
            metadata = trafilatura.extract_metadata(html)

            title = ""
            published_at = None

            if metadata:
                title = metadata.title or ""
                if metadata.date:
                    try:
                        # trafilatura returns date as string
                        published_at = datetime.fromisoformat(metadata.date)
                    except (ValueError, TypeError):
                        pass

            # Fallback: try to get title from HTML if not in metadata
            if not title:
                soup = BeautifulSoup(html, "html.parser")
                title_tag = soup.find("title")
                if title_tag:
                    title = title_tag.get_text(strip=True)
                else:
                    h1_tag = soup.find("h1")
                    if h1_tag:
                        title = h1_tag.get_text(strip=True)

            if not title:
                title = url  # Last resort: use URL as title

            return ExtractedArticle(
                url=url,
                title=title,
                content=extracted,
                published_at=published_at,
                source_url=source_url,
            )

        except Exception as e:
            logger.error(f"Error extracting article from {url}: {e}")
            return None
