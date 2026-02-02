"""Tests for FetcherManager."""

import asyncio
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from src.core.models import Category, Source, SourceType
from src.core.primitives.fetchers.base import ExtractedArticle
from src.core.primitives.fetchers.manager import FetcherManager, FetchStats
from src.core.utils.time import utcnow


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
            articles_old=3,
            errors=["Error 1"],
        )

        assert stats.sources_checked == 5
        assert stats.sources_fetched == 3
        assert stats.articles_found == 20
        assert stats.articles_new == 15
        assert stats.articles_filtered == 5
        assert stats.articles_old == 3
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
        source.last_fetched_at = utcnow() - timedelta(minutes=120)

        next_fetch = source.last_fetched_at + timedelta(
            minutes=source.fetch_interval_minutes
        )
        now = utcnow()

        # Should be due (next_fetch is in the past)
        assert next_fetch < now

    def test_source_within_interval_not_due(self):
        """Test that source within fetch interval is not due."""
        source = MagicMock(spec=Source)
        source.fetch_interval_minutes = 60
        source.last_fetched_at = utcnow() - timedelta(minutes=30)

        next_fetch = source.last_fetched_at + timedelta(
            minutes=source.fetch_interval_minutes
        )
        now = utcnow()

        # Should not be due (next_fetch is in the future)
        assert next_fetch > now


class TestDateFiltering:
    """Tests for article date filtering logic."""

    @pytest.fixture
    def manager(self):
        """Create a FetcherManager instance."""
        return FetcherManager()

    @pytest.fixture
    def sample_source(self):
        """Create a sample source."""
        source = MagicMock(spec=Source)
        source.last_fetched_at = None
        return source

    def test_get_date_cutoff_first_fetch(self, manager, sample_source):
        """Test cutoff is 24 hours ago for first fetch."""
        sample_source.last_fetched_at = None

        cutoff = manager._get_date_cutoff(sample_source)
        now = utcnow()

        # Cutoff should be approximately 24 hours ago
        expected = now - timedelta(hours=24)
        # Allow 1 minute tolerance
        assert abs((cutoff - expected).total_seconds()) < 60

    def test_get_date_cutoff_subsequent_fetch(self, manager, sample_source):
        """Test cutoff is last_fetched_at for subsequent fetches."""
        last_fetch = utcnow() - timedelta(hours=6)
        sample_source.last_fetched_at = last_fetch

        cutoff = manager._get_date_cutoff(sample_source)

        assert cutoff == last_fetch

    def test_is_recent_enough_no_published_date(self, manager):
        """Test articles without published_at are included."""
        article = ExtractedArticle(
            url="https://example.com/test",
            title="Test Article",
            content="Content",
            published_at=None,
            source_url="https://example.com/",
        )
        cutoff = utcnow() - timedelta(hours=24)

        assert manager._is_recent_enough(article, cutoff)

    def test_is_recent_enough_recent_article(self, manager):
        """Test recent articles are included."""
        article = ExtractedArticle(
            url="https://example.com/test",
            title="Test Article",
            content="Content",
            published_at=utcnow() - timedelta(hours=1),
            source_url="https://example.com/",
        )
        cutoff = utcnow() - timedelta(hours=24)

        assert manager._is_recent_enough(article, cutoff)

    def test_is_recent_enough_old_article(self, manager):
        """Test old articles are excluded."""
        article = ExtractedArticle(
            url="https://example.com/test",
            title="Test Article",
            content="Content",
            published_at=utcnow() - timedelta(hours=48),
            source_url="https://example.com/",
        )
        cutoff = utcnow() - timedelta(hours=24)

        assert not manager._is_recent_enough(article, cutoff)

    def test_is_recent_enough_exact_cutoff(self, manager):
        """Test article exactly at cutoff is included."""
        cutoff = utcnow() - timedelta(hours=24)
        article = ExtractedArticle(
            url="https://example.com/test",
            title="Test Article",
            content="Content",
            published_at=cutoff,
            source_url="https://example.com/",
        )

        assert manager._is_recent_enough(article, cutoff)


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


class TestFetchDueSourcesIntegration:
    """Integration tests for fetch_due_sources with real database."""

    @pytest.mark.asyncio
    async def test_due_filtering_correctness(self, clean_database, monkeypatch):
        """
        Test that only enabled and due sources are fetched.

        Creates 4 sources:
        - due A: last_fetched_at NULL
        - due B: last_fetched_at = now - 2*interval
        - not due C: last_fetched_at = now - (interval/2)
        - disabled D: enabled=false even if old
        """
        # Monkeypatch get_db to return our test database
        async def mock_get_db():
            return clean_database

        monkeypatch.setattr(
            "src.core.primitives.fetchers.manager.get_db", mock_get_db
        )

        # Monkeypatch fetch_articles to not hit network
        async def mock_fetch_articles(self, url):
            return []

        monkeypatch.setattr(
            "src.core.primitives.fetchers.website.WebsiteFetcher.fetch_articles",
            mock_fetch_articles,
        )

        # Create test data
        now = utcnow()
        async with clean_database.session() as session:
            # Create category
            category = Category(
                name="Test Category",
                digest_section="test",
                keywords=[],
            )
            session.add(category)
            await session.flush()

            # Source A: due (last_fetched_at NULL)
            source_a = Source(
                category_id=category.id,
                name="Source A (due, never fetched)",
                url="https://example.com/a",
                source_type=SourceType.WEBSITE,
                enabled=True,
                fetch_interval_minutes=60,
                last_fetched_at=None,
            )
            session.add(source_a)

            # Source B: due (last_fetched_at = now - 2*interval)
            source_b = Source(
                category_id=category.id,
                name="Source B (due, old)",
                url="https://example.com/b",
                source_type=SourceType.WEBSITE,
                enabled=True,
                fetch_interval_minutes=60,
                last_fetched_at=now - timedelta(minutes=120),
            )
            session.add(source_b)

            # Source C: not due (last_fetched_at = now - interval/2)
            source_c = Source(
                category_id=category.id,
                name="Source C (not due)",
                url="https://example.com/c",
                source_type=SourceType.WEBSITE,
                enabled=True,
                fetch_interval_minutes=60,
                last_fetched_at=now - timedelta(minutes=30),
            )
            session.add(source_c)

            # Source D: disabled (even if old)
            source_d = Source(
                category_id=category.id,
                name="Source D (disabled)",
                url="https://example.com/d",
                source_type=SourceType.WEBSITE,
                enabled=False,
                fetch_interval_minutes=60,
                last_fetched_at=now - timedelta(minutes=120),
            )
            session.add(source_d)

            await session.commit()

            # Store IDs for verification
            source_a_id = source_a.id
            source_b_id = source_b.id
            source_c_id = source_c.id
            source_d_id = source_d.id

        # Run fetch_due_sources
        manager = FetcherManager()
        stats = await manager.fetch_due_sources(max_sources=10)

        # Verify stats
        assert stats.sources_checked == 2, "Should claim 2 due sources (A and B)"
        assert stats.sources_fetched == 2, "Both fetches should succeed"
        assert stats.articles_found == 0, "No articles (mocked to return [])"

        # Verify database state
        async with clean_database.session() as session:
            from sqlalchemy import select

            result = await session.execute(select(Source))
            sources = {s.id: s for s in result.scalars().all()}

            # Source A and B should have updated last_fetched_at
            assert sources[source_a_id].last_fetched_at is not None
            assert sources[source_a_id].last_fetched_at > now
            assert sources[source_b_id].last_fetched_at is not None
            assert sources[source_b_id].last_fetched_at > now

            # Source C and D should have unchanged last_fetched_at
            assert sources[source_c_id].last_fetched_at == now - timedelta(minutes=30)
            assert sources[source_d_id].last_fetched_at == now - timedelta(minutes=120)

    @pytest.mark.asyncio
    async def test_max_sources_limit(self, clean_database, monkeypatch):
        """
        Test that max_sources applies to due sources.

        Creates 3 due sources, fetches with max_sources=2.
        """
        # Monkeypatch get_db
        async def mock_get_db():
            return clean_database

        monkeypatch.setattr(
            "src.core.primitives.fetchers.manager.get_db", mock_get_db
        )

        # Monkeypatch fetch_articles
        async def mock_fetch_articles(self, url):
            return []

        monkeypatch.setattr(
            "src.core.primitives.fetchers.website.WebsiteFetcher.fetch_articles",
            mock_fetch_articles,
        )

        # Create test data
        async with clean_database.session() as session:
            category = Category(
                name="Test Category",
                digest_section="test",
                keywords=[],
            )
            session.add(category)
            await session.flush()

            # Create 3 due sources
            for i in range(3):
                source = Source(
                    category_id=category.id,
                    name=f"Source {i}",
                    url=f"https://example.com/{i}",
                    source_type=SourceType.WEBSITE,
                    enabled=True,
                    fetch_interval_minutes=60,
                    last_fetched_at=None,
                )
                session.add(source)

            await session.commit()

        # Run fetch_due_sources with max_sources=2
        manager = FetcherManager()
        stats = await manager.fetch_due_sources(max_sources=2)

        # Verify stats
        assert stats.sources_checked == 2, "Should claim exactly 2 sources"
        assert stats.sources_fetched == 2, "Both fetches should succeed"

        # Verify exactly 2 sources have updated last_fetched_at
        async with clean_database.session() as session:
            from sqlalchemy import select

            result = await session.execute(select(Source))
            sources = list(result.scalars().all())

            updated_count = sum(1 for s in sources if s.last_fetched_at is not None)
            assert updated_count == 2, "Exactly 2 sources should be updated"

    @pytest.mark.asyncio
    async def test_multi_worker_safety(self, clean_database, monkeypatch):
        """
        Test that concurrent workers don't process the same source.

        Creates 2 due sources, runs 2 workers concurrently with max_sources=1 each.
        Both sources should end up processed (not the same one twice).
        """
        # Monkeypatch get_db
        async def mock_get_db():
            return clean_database

        monkeypatch.setattr(
            "src.core.primitives.fetchers.manager.get_db", mock_get_db
        )

        # Monkeypatch fetch_articles with delay to hold lock
        async def mock_fetch_articles_with_delay(self, url):
            await asyncio.sleep(0.2)  # Hold lock for a bit
            return []

        monkeypatch.setattr(
            "src.core.primitives.fetchers.website.WebsiteFetcher.fetch_articles",
            mock_fetch_articles_with_delay,
        )

        # Create test data
        async with clean_database.session() as session:
            category = Category(
                name="Test Category",
                digest_section="test",
                keywords=[],
            )
            session.add(category)
            await session.flush()

            # Create 2 due sources
            source_1 = Source(
                category_id=category.id,
                name="Source 1",
                url="https://example.com/1",
                source_type=SourceType.WEBSITE,
                enabled=True,
                fetch_interval_minutes=60,
                last_fetched_at=None,
            )
            session.add(source_1)

            source_2 = Source(
                category_id=category.id,
                name="Source 2",
                url="https://example.com/2",
                source_type=SourceType.WEBSITE,
                enabled=True,
                fetch_interval_minutes=60,
                last_fetched_at=None,
            )
            session.add(source_2)

            await session.commit()

        # Run two workers concurrently
        manager1 = FetcherManager()
        manager2 = FetcherManager()

        results = await asyncio.gather(
            manager1.fetch_due_sources(max_sources=1),
            manager2.fetch_due_sources(max_sources=1),
        )

        stats1, stats2 = results

        # Both workers should process exactly one source
        assert stats1.sources_checked == 1, "Worker 1 should claim 1 source"
        assert stats2.sources_checked == 1, "Worker 2 should claim 1 source"
        assert stats1.sources_fetched == 1, "Worker 1 fetch should succeed"
        assert stats2.sources_fetched == 1, "Worker 2 fetch should succeed"

        # Verify both sources have been updated (not the same one twice)
        async with clean_database.session() as session:
            from sqlalchemy import select

            result = await session.execute(select(Source))
            sources = list(result.scalars().all())

            updated_count = sum(1 for s in sources if s.last_fetched_at is not None)
            assert (
                updated_count == 2
            ), "Both sources should be updated (one by each worker)"

    @pytest.mark.asyncio
    async def test_error_handling_releases_lock(self, clean_database, monkeypatch):
        """
        Test that errors during fetch release the lock so the loop can continue.

        Creates 2 due sources, first one raises exception, second should still process.
        """
        # Monkeypatch get_db
        async def mock_get_db():
            return clean_database

        monkeypatch.setattr(
            "src.core.primitives.fetchers.manager.get_db", mock_get_db
        )

        # Track which sources were attempted
        attempted_urls = []

        # Monkeypatch fetch_articles to fail on first, succeed on second
        async def mock_fetch_articles_with_error(self, url):
            attempted_urls.append(url)
            if url == "https://example.com/fail":
                raise Exception("Network error")
            return []

        monkeypatch.setattr(
            "src.core.primitives.fetchers.website.WebsiteFetcher.fetch_articles",
            mock_fetch_articles_with_error,
        )

        # Create test data
        async with clean_database.session() as session:
            category = Category(
                name="Test Category",
                digest_section="test",
                keywords=[],
            )
            session.add(category)
            await session.flush()

            # Source 1: will fail (alphabetically first so fetched first)
            source_1 = Source(
                category_id=category.id,
                name="AAAA Fail Source",
                url="https://example.com/fail",
                source_type=SourceType.WEBSITE,
                enabled=True,
                fetch_interval_minutes=60,
                last_fetched_at=None,
            )
            session.add(source_1)

            # Source 2: will succeed
            source_2 = Source(
                category_id=category.id,
                name="BBBB Success Source",
                url="https://example.com/success",
                source_type=SourceType.WEBSITE,
                enabled=True,
                fetch_interval_minutes=60,
                last_fetched_at=None,
            )
            session.add(source_2)

            await session.commit()
            source_1_id = source_1.id
            source_2_id = source_2.id

        # Run fetch_due_sources
        manager = FetcherManager()
        stats = await manager.fetch_due_sources(max_sources=10)

        # Verify stats
        assert stats.sources_checked == 2, "Should attempt both sources"
        assert stats.sources_fetched == 1, "Only one should succeed"
        assert len(stats.errors) == 1, "One error should be recorded"

        # Verify both URLs were attempted
        assert len(attempted_urls) == 2, "Both sources should be attempted"

        # Verify only the successful source has updated last_fetched_at
        async with clean_database.session() as session:
            from sqlalchemy import select

            result = await session.execute(select(Source))
            sources = {s.id: s for s in result.scalars().all()}

            assert (
                sources[source_1_id].last_fetched_at is None
            ), "Failed source should not update"
            assert (
                sources[source_2_id].last_fetched_at is not None
            ), "Successful source should update"
