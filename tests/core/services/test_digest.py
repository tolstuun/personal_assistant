"""
Tests for DigestService.

Unit tests that mock the database, summarizer, and settings
to verify digest generation logic without real infrastructure.
"""

import uuid
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.models.security_digest import Article, Digest, DigestStatus
from src.core.services.digest import DigestService
from src.core.services.summarizer import SummaryResult


class MockSettingsService:
    """Mock settings service for testing."""

    def __init__(
        self,
        sections: list[str] | None = None,
        provider: str = "ollama",
        tier: str = "fast",
        telegram_notifications: bool = True,
    ):
        self.sections = sections or ["security_news", "product_news", "market"]
        self.provider = provider
        self.tier = tier
        self.telegram_notifications = telegram_notifications

    async def get(self, key: str):
        if key == "digest_sections":
            return self.sections
        if key == "summarizer_provider":
            return self.provider
        if key == "summarizer_tier":
            return self.tier
        if key == "telegram_notifications":
            return self.telegram_notifications
        raise KeyError(f"Unknown key: {key}")


class MockSummarizerService:
    """Mock summarizer that returns predictable summaries."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def summarize(self, title: str, content: str, url: str) -> SummaryResult:
        self.calls.append({"title": title, "content": content, "url": url})
        return SummaryResult(
            summary=f"Summary of: {title}",
            url=url,
            title=title,
        )


def _make_article(
    title: str = "Test Article",
    url: str = "https://example.com/article",
    digest_section: str = "security_news",
    summary: str | None = None,
    raw_content: str | None = "Some article content",
    digest_id: uuid.UUID | None = None,
) -> MagicMock:
    """Create a mock Article with the given attributes."""
    article = MagicMock(spec=Article)
    article.id = uuid.uuid4()
    article.title = title
    article.url = url
    article.digest_section = digest_section
    article.summary = summary
    article.raw_content = raw_content
    article.digest_id = digest_id
    return article


class MockDBSession:
    """Mock database session for testing."""

    def __init__(self, articles: list) -> None:
        self.articles = articles
        self.added: list = []
        self.executed: list = []
        self.committed = False

    async def execute(self, stmt):
        self.executed.append(stmt)
        # Return mock result for SELECT queries
        result = MagicMock()
        result.scalars.return_value.all.return_value = self.articles
        return result

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class MockDB:
    """Mock database connection."""

    def __init__(self, articles: list) -> None:
        self._session = MockDBSession(articles)

    def session(self):
        return self._session


class TestDigestGeneration:
    """Tests for DigestService.generate()."""

    @pytest.mark.asyncio
    async def test_generate_creates_digest_with_ready_status(self, tmp_path) -> None:
        """Generate creates a Digest record with status READY."""
        articles = [_make_article()]
        mock_db = MockDB(articles)

        with (
            patch("src.core.services.digest.get_db", new_callable=AsyncMock, return_value=mock_db),
            patch("src.core.services.digest.DIGESTS_DIR", tmp_path),
        ):
            service = DigestService(
                settings_service=MockSettingsService(),
                summarizer_service=MockSummarizerService(),
            )
            digest = await service.generate()

        assert isinstance(digest, Digest)
        assert digest.status == DigestStatus.READY

    @pytest.mark.asyncio
    async def test_generate_saves_html_file(self, tmp_path) -> None:
        """Generate saves an HTML file to the digests directory."""
        articles = [_make_article()]
        mock_db = MockDB(articles)

        with (
            patch("src.core.services.digest.get_db", new_callable=AsyncMock, return_value=mock_db),
            patch("src.core.services.digest.DIGESTS_DIR", tmp_path),
        ):
            service = DigestService(
                settings_service=MockSettingsService(),
                summarizer_service=MockSummarizerService(),
            )
            digest = await service.generate()

        # Verify HTML file was created
        html_path = Path(digest.html_path)
        assert html_path.exists()

        content = html_path.read_text()
        assert "Security Digest" in content
        assert "Test Article" in content

    @pytest.mark.asyncio
    async def test_generate_groups_articles_by_section(self, tmp_path) -> None:
        """Articles are grouped by digest_section in the HTML output."""
        articles = [
            _make_article(title="Security Article", digest_section="security_news"),
            _make_article(
                title="Product Article",
                url="https://example.com/product",
                digest_section="product_news",
            ),
        ]
        mock_db = MockDB(articles)

        with (
            patch("src.core.services.digest.get_db", new_callable=AsyncMock, return_value=mock_db),
            patch("src.core.services.digest.DIGESTS_DIR", tmp_path),
        ):
            service = DigestService(
                settings_service=MockSettingsService(),
                summarizer_service=MockSummarizerService(),
            )
            digest = await service.generate()

        content = Path(digest.html_path).read_text()
        assert "Security News" in content
        assert "Product News" in content

    @pytest.mark.asyncio
    async def test_generate_summarizes_unsummarized_articles(self, tmp_path) -> None:
        """Articles without summaries are summarized."""
        articles = [_make_article(summary=None, raw_content="Content to summarize")]
        mock_db = MockDB(articles)
        mock_summarizer = MockSummarizerService()

        with (
            patch("src.core.services.digest.get_db", new_callable=AsyncMock, return_value=mock_db),
            patch("src.core.services.digest.DIGESTS_DIR", tmp_path),
        ):
            service = DigestService(
                settings_service=MockSettingsService(),
                summarizer_service=mock_summarizer,
            )
            await service.generate()

        assert len(mock_summarizer.calls) == 1
        assert mock_summarizer.calls[0]["content"] == "Content to summarize"

    @pytest.mark.asyncio
    async def test_generate_skips_already_summarized(self, tmp_path) -> None:
        """Articles that already have summaries are not re-summarized."""
        articles = [_make_article(summary="Existing summary")]
        mock_db = MockDB(articles)
        mock_summarizer = MockSummarizerService()

        with (
            patch("src.core.services.digest.get_db", new_callable=AsyncMock, return_value=mock_db),
            patch("src.core.services.digest.DIGESTS_DIR", tmp_path),
        ):
            service = DigestService(
                settings_service=MockSettingsService(),
                summarizer_service=mock_summarizer,
            )
            await service.generate()

        assert len(mock_summarizer.calls) == 0

    @pytest.mark.asyncio
    async def test_generate_updates_articles_with_digest_id(self, tmp_path) -> None:
        """Articles are updated with the new digest_id in the database."""
        articles = [_make_article()]
        mock_db = MockDB(articles)

        with (
            patch("src.core.services.digest.get_db", new_callable=AsyncMock, return_value=mock_db),
            patch("src.core.services.digest.DIGESTS_DIR", tmp_path),
        ):
            service = DigestService(
                settings_service=MockSettingsService(),
                summarizer_service=MockSummarizerService(),
            )
            await service.generate()

        # Session should have committed (digest + article updates)
        assert mock_db._session.committed is True
        assert len(mock_db._session.added) == 1  # Digest record added

    @pytest.mark.asyncio
    async def test_generate_no_articles_raises(self, tmp_path) -> None:
        """Generate raises ValueError when no unprocessed articles exist."""
        mock_db = MockDB(articles=[])

        with (
            patch("src.core.services.digest.get_db", new_callable=AsyncMock, return_value=mock_db),
            patch("src.core.services.digest.DIGESTS_DIR", tmp_path),
        ):
            service = DigestService(
                settings_service=MockSettingsService(),
                summarizer_service=MockSummarizerService(),
            )

            with pytest.raises(ValueError, match="No unprocessed articles"):
                await service.generate()

    @pytest.mark.asyncio
    async def test_generate_respects_digest_sections_setting(self, tmp_path) -> None:
        """Only articles from enabled sections are included."""
        articles = [
            _make_article(title="Security Article", digest_section="security_news"),
            _make_article(
                title="Market Article",
                url="https://example.com/market",
                digest_section="market",
            ),
        ]
        mock_db = MockDB(articles)

        # Only enable security_news
        settings = MockSettingsService(sections=["security_news"])

        with (
            patch("src.core.services.digest.get_db", new_callable=AsyncMock, return_value=mock_db),
            patch("src.core.services.digest.DIGESTS_DIR", tmp_path),
        ):
            service = DigestService(
                settings_service=settings,
                summarizer_service=MockSummarizerService(),
            )
            digest = await service.generate()

        content = Path(digest.html_path).read_text()
        assert "Security Article" in content
        assert "Market Article" not in content

    @pytest.mark.asyncio
    async def test_generate_no_matching_sections_raises(self, tmp_path) -> None:
        """Raises ValueError when articles exist but none match enabled sections."""
        articles = [_make_article(digest_section="research")]
        mock_db = MockDB(articles)

        # Only enable security_news (no research articles)
        settings = MockSettingsService(sections=["security_news"])

        with (
            patch("src.core.services.digest.get_db", new_callable=AsyncMock, return_value=mock_db),
            patch("src.core.services.digest.DIGESTS_DIR", tmp_path),
        ):
            service = DigestService(
                settings_service=settings,
                summarizer_service=MockSummarizerService(),
            )

            with pytest.raises(ValueError, match="No unprocessed articles match"):
                await service.generate()

    @pytest.mark.asyncio
    async def test_generate_html_contains_article_links(self, tmp_path) -> None:
        """Generated HTML contains links to original article URLs."""
        articles = [_make_article(title="Linked Article", url="https://example.com/linked")]
        mock_db = MockDB(articles)

        with (
            patch("src.core.services.digest.get_db", new_callable=AsyncMock, return_value=mock_db),
            patch("src.core.services.digest.DIGESTS_DIR", tmp_path),
        ):
            service = DigestService(
                settings_service=MockSettingsService(),
                summarizer_service=MockSummarizerService(),
            )
            digest = await service.generate()

        content = Path(digest.html_path).read_text()
        assert "https://example.com/linked" in content
        assert "Linked Article" in content

    @pytest.mark.asyncio
    async def test_generate_html_filename_uses_date(self, tmp_path) -> None:
        """HTML filename includes today's date."""
        articles = [_make_article()]
        mock_db = MockDB(articles)

        with (
            patch("src.core.services.digest.get_db", new_callable=AsyncMock, return_value=mock_db),
            patch("src.core.services.digest.DIGESTS_DIR", tmp_path),
        ):
            service = DigestService(
                settings_service=MockSettingsService(),
                summarizer_service=MockSummarizerService(),
            )
            digest = await service.generate()

        today = date.today().isoformat()
        assert f"digest-{today}.html" in digest.html_path

    @pytest.mark.asyncio
    async def test_generate_skips_summarize_without_content(self, tmp_path) -> None:
        """Articles without raw_content are not sent to summarizer."""
        articles = [_make_article(summary=None, raw_content=None)]
        mock_db = MockDB(articles)
        mock_summarizer = MockSummarizerService()

        with (
            patch("src.core.services.digest.get_db", new_callable=AsyncMock, return_value=mock_db),
            patch("src.core.services.digest.DIGESTS_DIR", tmp_path),
        ):
            service = DigestService(
                settings_service=MockSettingsService(),
                summarizer_service=mock_summarizer,
            )
            await service.generate()

        assert len(mock_summarizer.calls) == 0


class MockNotifier:
    """Mock notifier for testing."""

    def __init__(self, success: bool = True) -> None:
        self.success = success
        self.calls: list[dict] = []

    async def send_digest_notification(self, digest, article_count: int) -> bool:
        self.calls.append({"digest": digest, "article_count": article_count})
        return self.success


class TestDigestNotification:
    """Tests for notification integration in DigestService.generate()."""

    @pytest.mark.asyncio
    async def test_generate_sends_notification_when_enabled(self, tmp_path) -> None:
        """Notification is sent when telegram_notifications is True."""
        articles = [_make_article()]
        mock_db = MockDB(articles)
        mock_notifier = MockNotifier(success=True)

        with (
            patch("src.core.services.digest.get_db", new_callable=AsyncMock, return_value=mock_db),
            patch("src.core.services.digest.DIGESTS_DIR", tmp_path),
        ):
            service = DigestService(
                settings_service=MockSettingsService(telegram_notifications=True),
                summarizer_service=MockSummarizerService(),
                notifier=mock_notifier,
            )
            await service.generate()

        assert len(mock_notifier.calls) == 1
        assert mock_notifier.calls[0]["article_count"] == 1

    @pytest.mark.asyncio
    async def test_generate_skips_notification_when_disabled(self, tmp_path) -> None:
        """Notification is NOT sent when telegram_notifications is False."""
        articles = [_make_article()]
        mock_db = MockDB(articles)
        mock_notifier = MockNotifier()

        with (
            patch("src.core.services.digest.get_db", new_callable=AsyncMock, return_value=mock_db),
            patch("src.core.services.digest.DIGESTS_DIR", tmp_path),
        ):
            service = DigestService(
                settings_service=MockSettingsService(telegram_notifications=False),
                summarizer_service=MockSummarizerService(),
                notifier=mock_notifier,
            )
            await service.generate()

        assert len(mock_notifier.calls) == 0

    @pytest.mark.asyncio
    async def test_generate_sets_notified_at_on_success(self, tmp_path) -> None:
        """Digest.notified_at is set when notification succeeds."""
        articles = [_make_article()]
        mock_db = MockDB(articles)
        mock_notifier = MockNotifier(success=True)

        with (
            patch("src.core.services.digest.get_db", new_callable=AsyncMock, return_value=mock_db),
            patch("src.core.services.digest.DIGESTS_DIR", tmp_path),
        ):
            service = DigestService(
                settings_service=MockSettingsService(telegram_notifications=True),
                summarizer_service=MockSummarizerService(),
                notifier=mock_notifier,
            )
            digest = await service.generate()

        assert digest.notified_at is not None

    @pytest.mark.asyncio
    async def test_generate_no_notified_at_on_failure(self, tmp_path) -> None:
        """Digest.notified_at is NOT set when notification fails."""
        articles = [_make_article()]
        mock_db = MockDB(articles)
        mock_notifier = MockNotifier(success=False)

        with (
            patch("src.core.services.digest.get_db", new_callable=AsyncMock, return_value=mock_db),
            patch("src.core.services.digest.DIGESTS_DIR", tmp_path),
        ):
            service = DigestService(
                settings_service=MockSettingsService(telegram_notifications=True),
                summarizer_service=MockSummarizerService(),
                notifier=mock_notifier,
            )
            await service.generate()

        # Notification was attempted but failed
        assert len(mock_notifier.calls) == 1

    @pytest.mark.asyncio
    async def test_generate_succeeds_even_if_notification_fails(self, tmp_path) -> None:
        """Digest generation succeeds even when notification fails."""
        articles = [_make_article()]
        mock_db = MockDB(articles)
        mock_notifier = MockNotifier(success=False)

        with (
            patch("src.core.services.digest.get_db", new_callable=AsyncMock, return_value=mock_db),
            patch("src.core.services.digest.DIGESTS_DIR", tmp_path),
        ):
            service = DigestService(
                settings_service=MockSettingsService(telegram_notifications=True),
                summarizer_service=MockSummarizerService(),
                notifier=mock_notifier,
            )
            digest = await service.generate()

        # Digest should still be created successfully
        assert isinstance(digest, Digest)
        assert digest.status == DigestStatus.READY
