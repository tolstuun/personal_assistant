"""
CLI script to test fetching from a source.

Usage:
    python -m src.core.primitives.fetchers.test_fetch <source_id>
    python -m src.core.primitives.fetchers.test_fetch --url <url>

Examples:
    # Fetch from a source in the database (dry run, doesn't save)
    python -m src.core.primitives.fetchers.test_fetch 123e4567-e89b-12d3-a456-426614174000

    # Test fetching from a URL directly
    python -m src.core.primitives.fetchers.test_fetch --url https://krebsonsecurity.com/
"""

import argparse
import asyncio
import sys


async def test_source(source_id: str) -> None:
    """
    Test fetching from a database source.

    Args:
        source_id: UUID of the source to fetch.
    """
    from src.core.primitives.fetchers.manager import FetcherManager

    print(f"Fetching from source: {source_id}")
    print("-" * 60)

    manager = FetcherManager()

    try:
        articles = await manager.fetch_source(source_id, save_to_db=False)
        print(f"\nFound {len(articles)} articles:\n")

        for i, article in enumerate(articles, 1):
            print(f"{i}. {article.title}")
            print(f"   URL: {article.url}")
            if article.published_at:
                print(f"   Date: {article.published_at}")
            print(f"   Content preview: {article.content[:200]}...")
            print()

    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except NotImplementedError as e:
        print(f"Not implemented: {e}")
        sys.exit(1)


async def test_url(url: str, max_articles: int = 10) -> None:
    """
    Test fetching from a URL directly.

    Args:
        url: URL to fetch articles from.
        max_articles: Maximum number of articles to fetch.
    """
    from src.core.primitives.fetchers.website import WebsiteFetcher

    print(f"Fetching from URL: {url}")
    print("-" * 60)

    fetcher = WebsiteFetcher()

    try:
        articles = await fetcher.fetch_articles(url, max_articles=max_articles)
        print(f"\nFound {len(articles)} articles:\n")

        for i, article in enumerate(articles, 1):
            print(f"{i}. {article.title}")
            print(f"   URL: {article.url}")
            if article.published_at:
                print(f"   Date: {article.published_at}")
            content_preview = article.content[:200].replace("\n", " ")
            print(f"   Content: {content_preview}...")
            print()

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def main() -> None:
    """Parse arguments and run the test."""
    parser = argparse.ArgumentParser(
        description="Test content fetching from a source or URL"
    )
    parser.add_argument(
        "source_id",
        nargs="?",
        help="UUID of the source to fetch from database",
    )
    parser.add_argument(
        "--url",
        help="URL to fetch directly (bypasses database)",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=10,
        help="Maximum number of articles to fetch (default: 10)",
    )

    args = parser.parse_args()

    if args.url:
        asyncio.run(test_url(args.url, args.max))
    elif args.source_id:
        asyncio.run(test_source(args.source_id))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
