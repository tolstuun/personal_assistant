"""
Twitter/X fetcher (stub implementation).

This is a placeholder for future Twitter integration.
Twitter API requires authentication and has rate limits.
"""

from src.core.primitives.fetchers.base import BaseFetcher, ExtractedArticle


class TwitterFetcher(BaseFetcher):
    """
    Fetches posts from Twitter/X.

    Currently a stub - raises NotImplementedError.
    Future implementation will use Twitter API v2.
    """

    async def fetch_articles(
        self,
        source_url: str,
        max_articles: int = 20,
    ) -> list[ExtractedArticle]:
        """
        Fetch tweets from a Twitter account or search.

        Args:
            source_url: Twitter profile URL or search query.
            max_articles: Maximum number of tweets to fetch.

        Returns:
            List of extracted articles.

        Raises:
            NotImplementedError: Twitter fetcher not yet implemented.
        """
        raise NotImplementedError(
            "Twitter fetcher is not yet implemented. "
            "Future version will support Twitter API v2."
        )
