"""
Base fetcher interface and common data structures.

All fetcher implementations inherit from BaseFetcher.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ExtractedArticle:
    """
    Article extracted from a source.

    This is the common format returned by all fetchers,
    regardless of source type (website, Twitter, Reddit).
    """

    url: str
    title: str
    content: str
    published_at: datetime | None
    source_url: str

    def __repr__(self) -> str:
        """Return string representation of article."""
        title_preview = self.title[:50] + "..." if len(self.title) > 50 else self.title
        return f"<ExtractedArticle(title='{title_preview}')>"


class BaseFetcher(ABC):
    """
    Abstract base class for content fetchers.

    Each fetcher implementation handles a specific source type
    (website, Twitter, Reddit) and returns a list of ExtractedArticle.
    """

    @abstractmethod
    async def fetch_articles(
        self,
        source_url: str,
        max_articles: int = 20,
    ) -> list[ExtractedArticle]:
        """
        Fetch articles from a source URL.

        Args:
            source_url: The URL to fetch articles from.
            max_articles: Maximum number of articles to fetch.

        Returns:
            List of extracted articles.
        """
        pass
