"""
Reddit fetcher (stub implementation).

This is a placeholder for future Reddit integration.
Reddit API requires authentication for higher rate limits.
"""

from src.core.primitives.fetchers.base import BaseFetcher, ExtractedArticle


class RedditFetcher(BaseFetcher):
    """
    Fetches posts from Reddit.

    Currently a stub - raises NotImplementedError.
    Future implementation will use Reddit API (PRAW).
    """

    async def fetch_articles(
        self,
        source_url: str,
        max_articles: int = 20,
    ) -> list[ExtractedArticle]:
        """
        Fetch posts from a subreddit or Reddit search.

        Args:
            source_url: Subreddit URL (e.g., https://reddit.com/r/netsec).
            max_articles: Maximum number of posts to fetch.

        Returns:
            List of extracted articles.

        Raises:
            NotImplementedError: Reddit fetcher not yet implemented.
        """
        raise NotImplementedError(
            "Reddit fetcher is not yet implemented. "
            "Future version will support Reddit API via PRAW."
        )
