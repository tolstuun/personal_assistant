"""
Digest generator service.

Collects unprocessed articles, summarizes them, groups by section,
and generates a standalone HTML digest page.
"""

import argparse
import asyncio
import logging
import sys
import uuid
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select, update

from src.core.models.security_digest import Article, Digest, DigestStatus
from src.core.services.notifier import TelegramNotifier
from src.core.services.settings import SettingsService
from src.core.services.summarizer import SummarizerService
from src.core.storage.postgres import get_db
from src.core.utils.time import utcnow_naive

logger = logging.getLogger(__name__)

# Directory for generated digest HTML files
DIGESTS_DIR = Path("data/digests")

# Jinja2 environment for digest template
_templates_dir = Path(__file__).parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(_templates_dir)), autoescape=True)


class DigestService:
    """
    Service for generating daily digests from unprocessed articles.

    Queries articles not yet assigned to a digest, summarizes them,
    groups by section, and outputs a standalone HTML page.
    """

    def __init__(
        self,
        settings_service: SettingsService | None = None,
        summarizer_service: SummarizerService | None = None,
        notifier: TelegramNotifier | None = None,
    ) -> None:
        """
        Initialize the digest service.

        Args:
            settings_service: Optional settings service instance.
            summarizer_service: Optional summarizer service instance.
            notifier: Optional telegram notifier instance.
        """
        self._settings = settings_service or SettingsService()
        self._summarizer = summarizer_service or SummarizerService(self._settings)
        self._notifier = notifier

    async def generate(self) -> Digest:
        """
        Generate a digest from all unprocessed articles.

        Collects articles where digest_id IS NULL, summarizes any that
        lack summaries, groups by section, renders HTML, and creates
        a Digest record.

        Returns:
            The created Digest record with status READY.

        Raises:
            ValueError: If no unprocessed articles are available.
        """
        db = await get_db()

        # 1. Query unprocessed articles
        async with db.session() as session:
            stmt = (
                select(Article)
                .where(Article.digest_id.is_(None))
                .order_by(Article.fetched_at.desc())
            )
            result = await session.execute(stmt)
            articles = list(result.scalars().all())

        if not articles:
            raise ValueError("No unprocessed articles available for digest generation")

        # 2. Get enabled digest sections from settings
        enabled_sections: list[str] = await self._settings.get("digest_sections")

        # 3. Filter articles to enabled sections only
        articles = [a for a in articles if a.digest_section in enabled_sections]

        if not articles:
            raise ValueError(
                "No unprocessed articles match the enabled digest sections: "
                + ", ".join(enabled_sections)
            )

        # 4. Summarize articles that don't have summaries yet
        summarized_count = 0
        for article in articles:
            if not article.summary and article.raw_content:
                result = await self._summarizer.summarize(
                    title=article.title,
                    content=article.raw_content,
                    url=article.url,
                )
                article.summary = result.summary
                summarized_count += 1

        logger.info(f"Summarized {summarized_count} articles")

        # 5. Group articles by digest_section
        sections: dict[str, list[Article]] = {}
        for section in enabled_sections:
            section_articles = [a for a in articles if a.digest_section == section]
            if section_articles:
                sections[section] = section_articles

        # 6. Render HTML
        today = date.today()
        now = utcnow_naive()

        template = _jinja_env.get_template("digest.html")
        html_content = template.render(
            date=today.strftime("%B %d, %Y"),
            sections=sections,
            generated_at=now.strftime("%Y-%m-%d %H:%M UTC"),
        )

        # 7. Save HTML to disk
        DIGESTS_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"digest-{today.isoformat()}.html"
        html_path = DIGESTS_DIR / filename
        html_path.write_text(html_content, encoding="utf-8")

        logger.info(f"Digest HTML saved to {html_path}")

        # 8. Create Digest record and update articles
        digest_id = uuid.uuid4()
        article_ids = [a.id for a in articles]

        async with db.session() as session:
            digest = Digest(
                id=digest_id,
                date=today,
                status=DigestStatus.READY,
                html_path=str(html_path),
                created_at=now,
            )
            session.add(digest)

            # Update articles with digest_id and summaries
            for article in articles:
                stmt = (
                    update(Article)
                    .where(Article.id == article.id)
                    .values(digest_id=digest_id, summary=article.summary)
                )
                await session.execute(stmt)

            await session.commit()

        logger.info(
            f"Digest created: {digest_id} with {len(article_ids)} articles "
            f"across {len(sections)} sections"
        )

        # 9. Send Telegram notification if enabled
        notify_enabled: bool = await self._settings.get("telegram_notifications")
        if notify_enabled:
            notifier = self._notifier or TelegramNotifier()
            sent = await notifier.send_digest_notification(
                digest=digest,
                article_count=len(articles),
            )
            if sent:
                async with db.session() as session:
                    stmt = (
                        update(Digest)
                        .where(Digest.id == digest_id)
                        .values(notified_at=utcnow_naive())
                    )
                    await session.execute(stmt)
                    await session.commit()
                digest.notified_at = utcnow_naive()

        return digest


# Singleton instance
_digest_service: DigestService | None = None


async def get_digest_service() -> DigestService:
    """Get the global digest service instance."""
    global _digest_service
    if _digest_service is None:
        _digest_service = DigestService()
    return _digest_service


# --- CLI Mode ---


async def generate_digest() -> None:
    """Generate a digest and print results."""
    service = DigestService()

    try:
        digest = await service.generate()
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print("Digest generated successfully!")
    print(f"  Date:     {digest.date}")
    print(f"  Status:   {digest.status.value}")
    print(f"  HTML:     {digest.html_path}")
    print(f"  Articles: {len(digest.articles) if digest.articles else 'see database'}")


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Digest Generator Service")
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate a digest from unprocessed articles",
    )
    args = parser.parse_args()

    if args.generate:
        asyncio.run(generate_digest())
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
