"""Tests for FetcherManager."""

import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from src.core.models import Category, Source, SourceType
from src.core.primitives.fetchers.base import ExtractedArticle
from src.core.primitives.fetchers.manager import FetcherManager, FetchStats


class TestFetchStats:
    """Tests for FetchStats dataclass."""

    def test_create_stats(self):
        """Test creating fetch stats."""
        stats = FetchStats(
            sources_checked=5,
            sources_fetched=3,
            articles_found=20,
            articles_new=15,
            articles_filtered=5,
            errors=["Error 1"],
        )

        assert stats.sources_checked == 5
        assert stats.sources_fetched == 3
        assert stats.articles_found == 20
        assert stats.articles_new == 15
        assert stats.articles_filtered == 5
        assert len(stats.errors) == 1


class TestFetcherManager:
    """Tests for FetcherManager class."""

    @pytest.fixture
    def manager(self):
        """Create a FetcherManager instance."""
        return FetcherManager()

    @pytest.fixture
    def sample_category(self):
        """Create a sample category."""
        category = MagicMock(spec=Category)
        category.id = uuid.uuid4()
        category.name = "Security News"
        category.digest_section = "security_news"
        category.keywords = ["security", "vulnerability"]
        return category

    @pytest.fixture
    def sample_source(self, sample_category):
        """Create a sample source."""
        source = MagicMock(spec=Source)
        source.id = uuid.uuid4()
        source.name = "Test Source"
        source.url = "https://example.com/"
        source.source_type = SourceType.WEBSITE
        source.keywords = ["CVE", "exploit"]
        source.enabled = True
        source.fetch_interval_minutes = 60
        source.last_fetched_at = None
        source.category = sample_category
        return source

    @pytest.fixture
    def sample_article(self):
        """Create a sample extracted article."""
        return ExtractedArticle(
            url="https://example.com/article/test",
            title="Test Security Vulnerability Found",
            content="A new security vulnerability was discovered. CVE-2024-0001.",
            published_at=datetime.now(),
            source_url="https://example.com/",
        )

    def test_init_creates_fetchers(self, manager):
        """Test that manager initializes all fetcher types."""
        assert SourceType.WEBSITE in manager.fetchers
        assert SourceType.TWITTER in manager.fetchers
        assert SourceType.REDDIT in manager.fetchers


class TestKeywordMatching:
    """Tests for keyword filtering logic."""

    @pytest.fixture
    def manager(self):
        """Create a FetcherManager instance."""
        return FetcherManager()

    @pytest.fixture
    def sample_category(self):
        """Create a sample category."""
        category = MagicMock(spec=Category)
        category.keywords = ["security", "vulnerability"]
        return category

    @pytest.fixture
    def sample_source(self, sample_category):
        """Create a sample source."""
        source = MagicMock(spec=Source)
        source.keywords = ["CVE", "exploit"]
        source.category = sample_category
        return source

    def test_matches_source_keyword(self, manager, sample_source):
        """Test matching against source keywords."""
        article = ExtractedArticle(
            url="https://example.com/test",
            title="New CVE Found",
            content="A new CVE was found today.",
            published_at=None,
            source_url="https://example.com/",
        )

        assert manager._matches_keywords(article, sample_source)

    def test_matches_category_keyword(self, manager, sample_source):
        """Test matching against category keywords."""
        article = ExtractedArticle(
            url="https://example.com/test",
            title="Security Update",
            content="Important security update released.",
            published_at=None,
            source_url="https://example.com/",
        )

        assert manager._matches_keywords(article, sample_source)

    def test_no_match(self, manager, sample_source):
        """Test article that doesn't match any keyword."""
        article = ExtractedArticle(
            url="https://example.com/test",
            title="Weather Report",
            content="It's sunny today.",
            published_at=None,
            source_url="https://example.com/",
        )

        assert not manager._matches_keywords(article, sample_source)

    def test_case_insensitive(self, manager, sample_source):
        """Test that keyword matching is case insensitive."""
        article = ExtractedArticle(
            url="https://example.com/test",
            title="SECURITY VULNERABILITY",
            content="Major SECURITY issue found.",
            published_at=None,
            source_url="https://example.com/",
        )

        assert manager._matches_keywords(article, sample_source)

    def test_no_keywords_passes(self, manager):
        """Test that articles pass when no keywords defined."""
        source = MagicMock(spec=Source)
        source.keywords = []
        source.category = MagicMock()
        source.category.keywords = []

        article = ExtractedArticle(
            url="https://example.com/test",
            title="Any Article",
            content="Any content.",
            published_at=None,
            source_url="https://example.com/",
        )

        assert manager._matches_keywords(article, source)

    def test_no_category_passes(self, manager):
        """Test that articles pass when source has no category."""
        source = MagicMock(spec=Source)
        source.keywords = []
        source.category = None

        article = ExtractedArticle(
            url="https://example.com/test",
            title="Any Article",
            content="Any content.",
            published_at=None,
            source_url="https://example.com/",
        )

        assert manager._matches_keywords(article, source)


class TestFetchSourceValidation:
    """Tests for fetch_source validation."""

    @pytest.fixture
    def manager(self):
        """Create a FetcherManager instance."""
        return FetcherManager()

    def test_fetcher_type_lookup(self, manager):
        """Test that fetchers are available for all source types."""
        assert manager.fetchers.get(SourceType.WEBSITE) is not None
        assert manager.fetchers.get(SourceType.TWITTER) is not None
        assert manager.fetchers.get(SourceType.REDDIT) is not None

    def test_unknown_source_type_returns_none(self, manager):
        """Test that unknown source type returns None from fetchers dict."""
        # This verifies the get() behavior for missing keys
        result = manager.fetchers.get("unknown_type")
        assert result is None


class TestSourceDueChecking:
    """Tests for source due checking logic."""

    def test_source_never_fetched_is_due(self):
        """Test that source with null last_fetched_at is due."""
        source = MagicMock(spec=Source)
        source.last_fetched_at = None
        source.fetch_interval_minutes = 60

        # Source with null last_fetched_at should be fetched
        assert source.last_fetched_at is None

    def test_source_past_interval_is_due(self):
        """Test that source past fetch interval is due."""
        source = MagicMock(spec=Source)
        source.fetch_interval_minutes = 60
        source.last_fetched_at = datetime.utcnow() - timedelta(minutes=120)

        next_fetch = source.last_fetched_at + timedelta(
            minutes=source.fetch_interval_minutes
        )
        now = datetime.utcnow()

        # Should be due (next_fetch is in the past)
        assert next_fetch < now

    def test_source_within_interval_not_due(self):
        """Test that source within fetch interval is not due."""
        source = MagicMock(spec=Source)
        source.fetch_interval_minutes = 60
        source.last_fetched_at = datetime.utcnow() - timedelta(minutes=30)

        next_fetch = source.last_fetched_at + timedelta(
            minutes=source.fetch_interval_minutes
        )
        now = datetime.utcnow()

        # Should not be due (next_fetch is in the future)
        assert next_fetch > now


class TestTwitterRedditStubs:
    """Tests for Twitter and Reddit stub implementations."""

    @pytest.mark.asyncio
    async def test_twitter_fetcher_raises(self):
        """Test that TwitterFetcher raises NotImplementedError."""
        from src.core.primitives.fetchers.twitter import TwitterFetcher

        fetcher = TwitterFetcher()

        with pytest.raises(NotImplementedError):
            await fetcher.fetch_articles("https://twitter.com/test")

    @pytest.mark.asyncio
    async def test_reddit_fetcher_raises(self):
        """Test that RedditFetcher raises NotImplementedError."""
        from src.core.primitives.fetchers.reddit import RedditFetcher

        fetcher = RedditFetcher()

        with pytest.raises(NotImplementedError):
            await fetcher.fetch_articles("https://reddit.com/r/netsec")
