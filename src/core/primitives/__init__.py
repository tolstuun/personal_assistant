"""
Primitives — atomic building blocks for agents.

Each primitive does ONE thing well.
Agents compose primitives into pipelines.
"""

from src.core.primitives.fetcher import (
    ContentType,
    Fetcher,
    FetcherConfig,
    FetchResult,
    fetch,
)

__all__ = [
    "ContentType",
    "Fetcher",
    "FetcherConfig",
    "FetchResult",
    "fetch",
]
