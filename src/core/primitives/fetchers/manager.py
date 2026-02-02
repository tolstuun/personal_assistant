"""
Fetcher manager for orchestrating content fetching.

This module coordinates fetching from all enabled sources,
handles deduplication, keyword filtering, and database storage.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, literal_column, or_, select
from sqlalchemy.orm import selectinload

from src.core.models import Article, Source, SourceType
from src.core.primitives.fetchers.base import ExtractedArticle
from src.core.primitives.fetchers.reddit import RedditFetcher
from src.core.primitives.fetchers.twitter import TwitterFetcher
from src.core.primitives.fetchers.website import WebsiteFetcher
from src.core.storage.postgres import get_db
from src.core.utils.time import utcnow_naive

logger = logging.getLogger(__name__)


@dataclass
class FetchStats:
    """Statistics from a fetch operation."""

    sources_checked: int
    sources_fetched: int
    articles_found: int
    articles_new: int
    articles_filtered: int
    articles_old: int
    errors: list[str]


class FetcherManager:
    """
    Manages fetching content from all sources.

    Responsibilities:
    - Query database for sources due for fetching
    - Dispatch to correct fetcher based on source type
    - Handle deduplication by URL
    - Apply keyword filtering
    - Store new articles in database
    - Update source.last_fetched_at
    """

    def __init__(self):
        """Initialize the fetcher manager with all fetcher types."""
        self.fetchers = {
            SourceType.WEBSITE: WebsiteFetcher(),
            SourceType.TWITTER: TwitterFetcher(),
            SourceType.REDDIT: RedditFetcher(),
        }

    async def fetch_due_sources(self, max_sources: int = 10) -> FetchStats:
        """
        Fetch content from all sources that are due.

        A source is due if:
        - It's enabled
        - last_fetched_at is NULL, OR
        - last_fetched_at <= (now_utc - fetch_interval_minutes)

        This method is safe for concurrent workers. It uses SELECT ... FOR UPDATE
        SKIP LOCKED to claim sources one at a time, preventing multiple workers
        from processing the same source simultaneously.

        Args:
            max_sources: Maximum number of sources to fetch in one run.

        Returns:
            Statistics about the fetch operation.
            - sources_checked: Number of sources successfully claimed (locked) for processing
            - sources_fetched: Number of sources where fetch completed successfully
        """
        stats = FetchStats(
            sources_checked=0,
            sources_fetched=0,
            articles_found=0,
            articles_new=0,
            articles_filtered=0,
            articles_old=0,
            errors=[],
        )

        db = await get_db()

        # Define due condition (evaluated in SQL for efficiency and correctness)
        now_utc = func.timezone("utc", func.now())
        interval_1m = literal_column("interval '1 minute'")
        due_when = or_(
            Source.last_fetched_at.is_(None),
            Source.last_fetched_at <= now_utc - (Source.fetch_interval_minutes * interval_1m),
        )

        # Track sources attempted in this run to avoid retrying failures
        attempted_source_ids: set[str] = set()

        # Process sources one at a time to avoid holding multiple locks
        for _ in range(max_sources):
            async with db.session() as session:
                # Select one due source with row lock (SKIP LOCKED for multi-worker safety)
                # Exclude sources already attempted in this run
                stmt = (
                    select(Source)
                    .options(selectinload(Source.category))
                    .where(
                        Source.enabled.is_(True),
                        due_when,
                        Source.id.notin_(attempted_source_ids) if attempted_source_ids else True,
                    )
                    .order_by(Source.last_fetched_at.asc().nullsfirst())
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )

                result = await session.execute(stmt)
                source = result.scalar_one_or_none()

                if not source:
                    # No more due sources available
                    break

                # Mark as attempted
                attempted_source_ids.add(source.id)
                stats.sources_checked += 1

                # Fetch from this source (lock held until commit/rollback)
                try:
                    source_stats = await self._fetch_source(session, source)
                    stats.sources_fetched += 1
                    stats.articles_found += source_stats["found"]
                    stats.articles_new += source_stats["saved"]
                    stats.articles_filtered += source_stats["filtered"]
                    stats.articles_old += source_stats["old"]
                except NotImplementedError as e:
                    # Expected for Twitter/Reddit stubs
                    logger.info(f"Source {source.name}: {e}")
                    stats.errors.append(f"{source.name}: {str(e)}")
                    await session.rollback()  # Release lock immediately
                except Exception as e:
                    logger.error(f"Error fetching {source.name}: {e}")
                    stats.errors.append(f"{source.name}: {str(e)}")
                    await session.rollback()  # Release lock immediately

        return stats

    async def fetch_source(
        self,
        source_id: str,
        save_to_db: bool = True,
    ) -> dict:
        """
        Fetch content from a specific source by ID.

        Args:
            source_id: UUID of the source to fetch.
            save_to_db: Whether to save articles to database.

        Returns:
            Dict with stats: articles_found, articles_saved, articles_old,
            articles_duplicate, articles_filtered.
        """
        db = await get_db()

        async with db.session() as session:
            stmt = (
                select(Source)
                .options(selectinload(Source.category))
                .where(Source.id == source_id)
            )
            result = await session.execute(stmt)
            source = result.scalar_one_or_none()

            if not source:
                raise ValueError(f"Source not found: {source_id}")

            fetcher = self.fetchers.get(source.source_type)
            if not fetcher:
                raise ValueError(f"No fetcher for source type: {source.source_type}")

            articles = await fetcher.fetch_articles(source.url)

            stats = {
                "articles_found": len(articles),
                "articles_saved": 0,
                "articles_old": 0,
                "articles_duplicate": 0,
                "articles_filtered": 0,
            }

            if save_to_db:
                save_stats = await self._save_articles(session, source, articles)
                stats["articles_saved"] = save_stats["saved"]
                stats["articles_old"] = save_stats["old"]
                stats["articles_duplicate"] = save_stats["duplicate"]
                stats["articles_filtered"] = save_stats["filtered"]

                source.last_fetched_at = utcnow_naive()
                await session.commit()

                logger.info(
                    f"Source {source.name}: found {stats['articles_found']}, "
                    f"saved {stats['articles_saved']}, old {stats['articles_old']}, "
                    f"duplicate {stats['articles_duplicate']}"
                )

            return stats

    async def _fetch_source(self, session, source: Source) -> dict:
        """
        Fetch and store articles from a single source.

        Args:
            session: Database session.
            source: Source to fetch from.

        Returns:
            Dict with stats: found, saved, filtered, old, duplicate.
        """
        logger.info(f"Fetching from source: {source.name} ({source.source_type.value})")

        fetcher = self.fetchers.get(source.source_type)
        if not fetcher:
            raise ValueError(f"No fetcher for source type: {source.source_type}")

        # Fetch articles
        articles = await fetcher.fetch_articles(source.url)

        # Save articles and get stats
        save_stats = await self._save_articles(session, source, articles)

        stats = {
            "found": len(articles),
            "saved": save_stats["saved"],
            "filtered": save_stats["filtered"],
            "old": save_stats["old"],
            "duplicate": save_stats["duplicate"],
        }

        # Update last_fetched_at
        source.last_fetched_at = utcnow_naive()
        await session.commit()

        logger.info(
            f"Source {source.name}: found {stats['found']}, "
            f"saved {stats['saved']}, filtered {stats['filtered']}, "
            f"old {stats['old']}, duplicate {stats['duplicate']}"
        )

        return stats

    async def _save_articles(
        self,
        session,
        source: Source,
        articles: list[ExtractedArticle],
    ) -> dict:
        """
        Save articles to database with deduplication, date, and keyword filtering.

        Args:
            session: Database session.
            source: Source the articles came from.
            articles: List of extracted articles.

        Returns:
            Dict with keys: saved, filtered, old, duplicate.
        """
        stats = {
            "saved": 0,
            "filtered": 0,
            "old": 0,
            "duplicate": 0,
        }

        # Calculate date cutoff for filtering
        cutoff_date = self._get_date_cutoff(source)

        for article in articles:
            # Check if URL already exists (deduplication)
            existing = await session.execute(
                select(Article).where(Article.url == article.url)
            )
            if existing.scalar_one_or_none():
                logger.debug(f"Skipping duplicate: {article.url}")
                stats["duplicate"] += 1
                continue

            # Apply date filtering
            if not self._is_recent_enough(article, cutoff_date):
                logger.debug(f"Filtered by date: {article.title} ({article.published_at})")
                stats["old"] += 1
                continue

            # Apply keyword filtering
            if not self._matches_keywords(article, source):
                logger.debug(f"Filtered by keywords: {article.title}")
                stats["filtered"] += 1
                continue

            # Create new article
            db_article = Article(
                source_id=source.id,
                url=article.url,
                title=article.title,
                raw_content=article.content,
                published_at=article.published_at,
                digest_section=source.category.digest_section if source.category else None,
                fetched_at=utcnow_naive(),
            )
            session.add(db_article)
            stats["saved"] += 1

        await session.flush()
        return stats

    def _get_date_cutoff(self, source: Source) -> datetime:
        """
        Calculate the date cutoff for article filtering.

        Args:
            source: The source being fetched.

        Returns:
            Articles older than this datetime will be filtered out.
        """
        if source.last_fetched_at is not None:
            # Use last fetch time as cutoff
            return source.last_fetched_at
        else:
            # First fetch: only keep articles from last 24 hours
            return utcnow_naive() - timedelta(hours=24)

    def _is_recent_enough(
        self,
        article: ExtractedArticle,
        cutoff_date: datetime,
    ) -> bool:
        """
        Check if article is recent enough to be included.

        Args:
            article: The extracted article.
            cutoff_date: Articles older than this are filtered out.

        Returns:
            True if article should be included.
        """
        # If no published date, assume it's recent (include it)
        if article.published_at is None:
            return True

        return article.published_at >= cutoff_date

    def _matches_keywords(
        self,
        article: ExtractedArticle,
        source: Source,
    ) -> bool:
        """
        Check if article matches source/category keywords.

        Args:
            article: The extracted article.
            source: The source with keywords.

        Returns:
            True if article matches keywords or no keywords defined.
        """
        # Collect all keywords
        keywords: set[str] = set()
        if source.keywords:
            keywords.update(source.keywords)
        if source.category and source.category.keywords:
            keywords.update(source.category.keywords)

        # If no keywords defined, everything passes
        if not keywords:
            return True

        # Check if any keyword appears in title or content
        text = f"{article.title} {article.content}".lower()
        return any(kw.lower() in text for kw in keywords)
