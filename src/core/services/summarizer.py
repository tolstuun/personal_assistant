"""
Summarizer service for generating AI summaries of articles.

Uses the LLM router with configurable provider/tier from DB settings.
Falls back to article title if summarization fails for any reason.
"""

import argparse
import asyncio
import json
import logging
import sys
import uuid
from dataclasses import dataclass, asdict

from src.core.llm.router import get_llm
from src.core.services.settings import SettingsService

logger = logging.getLogger(__name__)

# JSON schema for LLM response
SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "description": "A 2-3 sentence summary of the article"
        }
    },
    "required": ["summary"]
}

# Prompt template for summarization
SUMMARY_PROMPT = """You are a technical news summarizer. Your task is to write a concise \
2-3 sentence summary of the following article.

Rules:
- Write exactly 2-3 sentences
- Focus on the main point and key facts
- Be objective and factual
- Do not include opinions or speculation
- Do not mention that this is a summary

Article Title: {title}

Article Content:
{content}

Respond with JSON only:
{{"summary": "Your 2-3 sentence summary here"}}"""


@dataclass
class SummaryResult:
    """Result of article summarization."""

    summary: str
    url: str
    title: str


class SummarizerService:
    """
    Service for generating AI summaries of articles.

    Uses the LLM router with provider/tier from database settings.
    Always returns a result - falls back to title if summarization fails.
    """

    def __init__(self, settings_service: SettingsService | None = None) -> None:
        """
        Initialize the summarizer service.

        Args:
            settings_service: Optional settings service instance.
                              Creates a new one if not provided.
        """
        self._settings = settings_service or SettingsService()

    async def summarize(self, title: str, content: str, url: str) -> SummaryResult:
        """
        Generate a summary for an article.

        Args:
            title: Article title.
            content: Article raw content.
            url: Article URL.

        Returns:
            SummaryResult with summary, url, and title.
            On any error, summary will be the title.
        """
        try:
            # Get provider/tier from settings
            provider = await self._settings.get("summarizer_provider")
            tier = await self._settings.get("summarizer_tier")

            logger.debug(f"Summarizing '{title}' with {provider}/{tier}")

            # Get LLM instance with cheap, stable config
            llm = get_llm(
                provider=provider,
                tier=tier,
                temperature=0.2,
                max_tokens=200,
            )

            # Build prompt
            prompt = SUMMARY_PROMPT.format(title=title, content=content)

            # Call LLM
            result = await llm.complete_json(prompt, schema=SUMMARY_SCHEMA)

            # Validate and extract summary
            summary = result.get("summary", "")
            if not isinstance(summary, str) or not summary.strip():
                logger.warning(f"Empty or invalid summary for '{title}', using title")
                return SummaryResult(summary=title, url=url, title=title)

            return SummaryResult(summary=summary.strip(), url=url, title=title)

        except Exception as e:
            # Log and fallback to title - never crash
            logger.warning(f"Summarization failed for '{title}': {e}")
            return SummaryResult(summary=title, url=url, title=title)


# Singleton instance
_summarizer_service: SummarizerService | None = None


async def get_summarizer_service() -> SummarizerService:
    """Get the global summarizer service instance."""
    global _summarizer_service
    if _summarizer_service is None:
        _summarizer_service = SummarizerService()
    return _summarizer_service


# --- CLI Test Mode ---

async def test_summarize(article_id: str) -> None:
    """
    Test summarization with a real article from the database.

    Args:
        article_id: UUID of the article to summarize.
    """
    from sqlalchemy import select

    from src.core.models.security_digest import Article
    from src.core.storage.postgres import get_db

    # Parse UUID
    try:
        article_uuid = uuid.UUID(article_id)
    except ValueError:
        print(f"Error: Invalid article ID format: {article_id}", file=sys.stderr)
        sys.exit(1)

    # Get article from database
    db = await get_db()
    async with db.session() as session:
        stmt = select(Article).where(Article.id == article_uuid)
        result = await session.execute(stmt)
        article = result.scalar_one_or_none()

    if article is None:
        print(f"Error: Article not found: {article_id}", file=sys.stderr)
        sys.exit(1)

    if not article.raw_content:
        print(f"Error: Article has no content: {article_id}", file=sys.stderr)
        sys.exit(1)

    # Run summarization
    service = SummarizerService()
    result = await service.summarize(
        title=article.title,
        content=article.raw_content,
        url=article.url,
    )

    # Output as pretty JSON
    output = asdict(result)
    print(json.dumps(output, indent=2, ensure_ascii=False))


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="LLM Summarizer Service")
    parser.add_argument(
        "--test",
        metavar="ARTICLE_ID",
        help="Test summarization with a real article from the database",
    )
    args = parser.parse_args()

    if args.test:
        asyncio.run(test_summarize(args.test))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
