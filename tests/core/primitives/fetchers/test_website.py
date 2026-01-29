"""Tests for WebsiteFetcher."""

from unittest.mock import AsyncMock, patch

import pytest

from src.core.primitives.fetcher import FetchResult, ContentType
from src.core.primitives.fetchers.base import ExtractedArticle
from src.core.primitives.fetchers.website import WebsiteFetcher


class TestExtractedArticle:
    """Tests for ExtractedArticle dataclass."""

    def test_create_article(self):
        """Test creating an extracted article."""
        article = ExtractedArticle(
            url="https://example.com/article",
            title="Test Article",
            content="This is the content.",
            published_at=None,
            source_url="https://example.com/",
        )

        assert article.url == "https://example.com/article"
        assert article.title == "Test Article"
        assert article.content == "This is the content."
        assert article.published_at is None
        assert article.source_url == "https://example.com/"

    def test_repr_short_title(self):
        """Test string representation with short title."""
        article = ExtractedArticle(
            url="https://example.com/article",
            title="Short",
            content="Content",
            published_at=None,
            source_url="https://example.com/",
        )

        assert "Short" in repr(article)
        assert "..." not in repr(article)

    def test_repr_long_title(self):
        """Test string representation with long title is truncated."""
        long_title = "A" * 100
        article = ExtractedArticle(
            url="https://example.com/article",
            title=long_title,
            content="Content",
            published_at=None,
            source_url="https://example.com/",
        )

        assert "..." in repr(article)
        assert len(repr(article)) < len(long_title) + 50


class TestWebsiteFetcher:
    """Tests for WebsiteFetcher class."""

    @pytest.fixture
    def fetcher(self):
        """Create a WebsiteFetcher instance."""
        return WebsiteFetcher()

    def test_init_default_config(self, fetcher):
        """Test default configuration."""
        assert fetcher.concurrent_limit == 5
        assert fetcher.fetcher.config.timeout == 30.0
        assert fetcher.fetcher.config.max_retries == 2

    def test_init_custom_config(self):
        """Test custom configuration."""
        fetcher = WebsiteFetcher(
            timeout=60.0,
            max_retries=5,
            concurrent_limit=10,
        )

        assert fetcher.concurrent_limit == 10
        assert fetcher.fetcher.config.timeout == 60.0
        assert fetcher.fetcher.config.max_retries == 5


class TestLinkExtraction:
    """Tests for article link extraction."""

    @pytest.fixture
    def fetcher(self):
        """Create a WebsiteFetcher instance."""
        return WebsiteFetcher()

    def test_extract_simple_links(self, fetcher):
        """Test extracting links from simple HTML."""
        html = """
        <html>
        <body>
            <article>
                <a href="/article/2024/01/security-update">Security Update</a>
                <a href="/article/2024/01/new-vulnerability">New Vulnerability</a>
            </article>
        </body>
        </html>
        """
        base_url = "https://example.com/"

        links = fetcher._extract_article_links(html, base_url)

        assert len(links) == 2
        assert "https://example.com/article/2024/01/security-update" in links
        assert "https://example.com/article/2024/01/new-vulnerability" in links

    def test_skip_nav_footer_links(self, fetcher):
        """Test that navigation and footer links are skipped."""
        html = """
        <html>
        <body>
            <nav>
                <a href="/about">About</a>
                <a href="/contact">Contact</a>
            </nav>
            <main>
                <a href="/article/good-article">Good Article</a>
            </main>
            <footer>
                <a href="/privacy">Privacy</a>
            </footer>
        </body>
        </html>
        """
        base_url = "https://example.com/"

        links = fetcher._extract_article_links(html, base_url)

        assert len(links) == 1
        assert "https://example.com/article/good-article" in links

    def test_skip_category_and_tag_links(self, fetcher):
        """Test that category and tag links are skipped."""
        html = """
        <html>
        <body>
            <a href="/category/security">Security</a>
            <a href="/tag/cve">CVE</a>
            <a href="/article/real-article">Real Article</a>
        </body>
        </html>
        """
        base_url = "https://example.com/"

        links = fetcher._extract_article_links(html, base_url)

        assert len(links) == 1
        assert "https://example.com/article/real-article" in links

    def test_deduplicate_links(self, fetcher):
        """Test that duplicate links are removed."""
        html = """
        <html>
        <body>
            <a href="/article/same">Same Article</a>
            <a href="/article/same">Same Article Again</a>
            <a href="/article/same#section">Same with Fragment</a>
        </body>
        </html>
        """
        base_url = "https://example.com/"

        links = fetcher._extract_article_links(html, base_url)

        # All three should resolve to the same URL
        assert len(links) == 1

    def test_absolute_urls(self, fetcher):
        """Test handling of absolute URLs."""
        html = """
        <html>
        <body>
            <a href="https://example.com/article/absolute">Absolute Link</a>
            <a href="/article/relative">Relative Link</a>
        </body>
        </html>
        """
        base_url = "https://example.com/"

        links = fetcher._extract_article_links(html, base_url)

        assert len(links) == 2
        assert all(link.startswith("https://") for link in links)

    def test_skip_javascript_and_mailto_links(self, fetcher):
        """Test that javascript: and mailto: links are skipped."""
        html = """
        <html>
        <body>
            <a href="javascript:void(0)">JS Link</a>
            <a href="mailto:test@example.com">Email</a>
            <a href="tel:+1234567890">Phone</a>
            <a href="/article/valid">Valid Article</a>
        </body>
        </html>
        """
        base_url = "https://example.com/"

        links = fetcher._extract_article_links(html, base_url)

        assert len(links) == 1
        assert "https://example.com/article/valid" in links

    def test_skip_short_paths(self, fetcher):
        """Test that very short paths (likely homepage) are skipped."""
        html = """
        <html>
        <body>
            <a href="/">Home</a>
            <a href="/a">Too Short</a>
            <a href="/article/good-long-path">Good Article</a>
        </body>
        </html>
        """
        base_url = "https://example.com/"

        links = fetcher._extract_article_links(html, base_url)

        assert len(links) == 1
        assert "https://example.com/article/good-long-path" in links


class TestLooksLikeArticleUrl:
    """Tests for article URL pattern detection."""

    @pytest.fixture
    def fetcher(self):
        """Create a WebsiteFetcher instance."""
        return WebsiteFetcher()

    def test_article_path(self, fetcher):
        """Test detection of /article/ path."""
        assert fetcher._looks_like_article_url("https://example.com/article/test")

    def test_blog_path(self, fetcher):
        """Test detection of /blog/ path."""
        assert fetcher._looks_like_article_url("https://example.com/blog/test")

    def test_news_path(self, fetcher):
        """Test detection of /news/ path."""
        assert fetcher._looks_like_article_url("https://example.com/news/test")

    def test_year_in_path(self, fetcher):
        """Test detection of year in URL path."""
        assert fetcher._looks_like_article_url("https://example.com/2024/01/test")

    def test_not_article_url(self, fetcher):
        """Test non-article URL."""
        assert not fetcher._looks_like_article_url("https://example.com/about")
        assert not fetcher._looks_like_article_url("https://example.com/contact")


class TestFetchArticles:
    """Tests for the fetch_articles method."""

    @pytest.fixture
    def fetcher(self):
        """Create a WebsiteFetcher instance."""
        return WebsiteFetcher()

    @pytest.fixture
    def mock_listing_page(self):
        """Mock listing page HTML."""
        return """
        <html>
        <body>
            <article>
                <a href="/article/test-1">Test Article 1</a>
                <a href="/article/test-2">Test Article 2</a>
            </article>
        </body>
        </html>
        """

    @pytest.fixture
    def mock_article_page(self):
        """Mock article page HTML."""
        return """
        <html>
        <head><title>Test Article</title></head>
        <body>
            <article>
                <h1>Test Article Title</h1>
                <p>This is the article content. It has multiple paragraphs.</p>
                <p>Here is another paragraph with more information.</p>
            </article>
        </body>
        </html>
        """

    @pytest.mark.asyncio
    async def test_fetch_articles_success(
        self, fetcher, mock_listing_page, mock_article_page
    ):
        """Test successful article fetching."""
        from datetime import datetime

        listing_result = FetchResult(
            url="https://example.com/",
            status_code=200,
            content_type=ContentType.HTML,
            content=mock_listing_page.encode(),
            text=mock_listing_page,
            headers={},
            fetched_at=datetime.now(),
            elapsed_ms=100,
        )

        article_result = FetchResult(
            url="https://example.com/article/test-1",
            status_code=200,
            content_type=ContentType.HTML,
            content=mock_article_page.encode(),
            text=mock_article_page,
            headers={},
            fetched_at=datetime.now(),
            elapsed_ms=100,
        )

        with patch.object(
            fetcher.fetcher, "fetch", new_callable=AsyncMock
        ) as mock_fetch:
            # First call returns listing, subsequent calls return article
            mock_fetch.side_effect = [listing_result, article_result, article_result]

            articles = await fetcher.fetch_articles("https://example.com/", max_articles=2)

            assert len(articles) == 2
            assert mock_fetch.call_count == 3  # 1 listing + 2 articles

    @pytest.mark.asyncio
    async def test_fetch_articles_listing_fails(self, fetcher):
        """Test handling of listing page fetch failure."""
        from datetime import datetime

        failed_result = FetchResult(
            url="https://example.com/",
            status_code=500,
            content_type=ContentType.HTML,
            content=b"",
            text="",
            headers={},
            fetched_at=datetime.now(),
            elapsed_ms=100,
        )

        with patch.object(
            fetcher.fetcher, "fetch", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = failed_result

            articles = await fetcher.fetch_articles("https://example.com/")

            assert len(articles) == 0

    @pytest.mark.asyncio
    async def test_fetch_articles_respects_max(self, fetcher, mock_listing_page):
        """Test that max_articles limit is respected."""
        from datetime import datetime

        listing_result = FetchResult(
            url="https://example.com/",
            status_code=200,
            content_type=ContentType.HTML,
            content=mock_listing_page.encode(),
            text=mock_listing_page,
            headers={},
            fetched_at=datetime.now(),
            elapsed_ms=100,
        )

        with patch.object(
            fetcher.fetcher, "fetch", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = listing_result

            # Only ask for 1 article
            await fetcher.fetch_articles("https://example.com/", max_articles=1)

            # Should be 2 calls: 1 listing + 1 article
            assert mock_fetch.call_count == 2
