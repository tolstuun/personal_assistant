"""
Content fetchers for Security Digest.

This module provides fetchers for different source types:
- WebsiteFetcher: Fetch articles from websites using trafilatura
- TwitterFetcher: Fetch from Twitter/X (stub)
- RedditFetcher: Fetch from Reddit (stub)
- FetcherManager: Orchestrates fetching from all sources
"""

from src.core.primitives.fetchers.base import BaseFetcher, ExtractedArticle
from src.core.primitives.fetchers.manager import FetcherManager
from src.core.primitives.fetchers.website import WebsiteFetcher

__all__ = [
    "BaseFetcher",
    "ExtractedArticle",
    "FetcherManager",
    "WebsiteFetcher",
]
