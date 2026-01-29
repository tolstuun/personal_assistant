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


async def test_source(source_id: str, save: bool = False) -> None:
    """
    Test fetching from a database source.

    Args:
        source_id: UUID of the source to fetch.
        save: Whether to save articles to database.
    """
    from src.core.primitives.fetchers.manager import FetcherManager
    from src.core.primitives.fetchers.website import WebsiteFetcher
    from src.core.models import Source, SourceType
    from src.core.storage.postgres import get_db
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    print(f"Fetching from source: {source_id}")
    print("-" * 60)

    try:
        if save:
            # Use manager to fetch and save
            manager = FetcherManager()
            stats = await manager.fetch_source(source_id, save_to_db=True)
            print("\nFetch complete:")
            print(f"  Found: {stats['articles_found']}")
            print(f"  Saved: {stats['articles_saved']}")
            print(f"  Old (filtered by date): {stats['articles_old']}")
            print(f"  Duplicate: {stats['articles_duplicate']}")
            print(f"  Filtered (by keywords): {stats['articles_filtered']}")
        else:
            # Dry run: fetch but don't save
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
                    print(f"Error: Source not found: {source_id}")
                    sys.exit(1)

                if source.source_type != SourceType.WEBSITE:
                    print(f"Error: Only website sources are supported (got {source.source_type})")
                    sys.exit(1)

                fetcher = WebsiteFetcher()
                articles = await fetcher.fetch_articles(source.url)

                print(f"\nFound {len(articles)} articles (dry run, not saved):\n")

                for i, article in enumerate(articles, 1):
                    print(f"{i}. {article.title}")
                    print(f"   URL: {article.url}")
                    if article.published_at:
                        print(f"   Date: {article.published_at}")
                    content_preview = article.content[:200].replace("\n", " ")
                    print(f"   Content: {content_preview}...")
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
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save articles to database (default: dry run)",
    )

    args = parser.parse_args()

    if args.url:
        asyncio.run(test_url(args.url, args.max))
    elif args.source_id:
        asyncio.run(test_source(args.source_id, save=args.save))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
