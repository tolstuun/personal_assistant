"""
Telegram notification service.

Lightweight service for sending proactive Telegram messages.
Separate from the full TelegramBot class (which handles webhooks
and commands) — this only sends notifications.
"""

import logging
from pathlib import Path

from telegram import Bot

from src.core.config import get_config
from src.core.models.security_digest import Digest

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Service for sending Telegram notifications.

    Uses the telegram.Bot API directly to send messages to
    configured users. Never raises exceptions — returns True/False
    and logs errors.
    """

    def __init__(self, token: str | None = None, chat_ids: list[int] | None = None,
                 base_url: str | None = None) -> None:
        """
        Initialize the notifier.

        Args:
            token: Telegram bot token. Read from config if not provided.
            chat_ids: Chat IDs to send to. Read from config if not provided.
            base_url: Server base URL for digest links. Read from config if not provided.
        """
        if token is None or chat_ids is None or base_url is None:
            config = get_config()
            tg_config = config.get("telegram", {})

        self._token = token or tg_config.get("token", "")
        self._chat_ids = chat_ids if chat_ids is not None else tg_config.get("allowed_users", [])
        self._base_url = base_url or tg_config.get("webhook_url", "")

    async def send_digest_notification(self, digest: Digest, article_count: int) -> bool:
        """
        Send a digest notification to all configured users.

        Args:
            digest: The generated Digest record.
            article_count: Number of articles in the digest.

        Returns:
            True if notification was sent successfully, False otherwise.
        """
        if not self._token:
            logger.warning("Telegram token not configured, skipping notification")
            return False

        if not self._chat_ids:
            logger.warning("No Telegram chat IDs configured, skipping notification")
            return False

        # Build digest URL from html_path filename
        filename = Path(digest.html_path).name if digest.html_path else ""
        digest_url = f"{self._base_url}/digests/{filename}" if filename else ""

        # Build message
        message = (
            f"<b>Security Digest — {digest.date}</b>\n\n"
            f"{article_count} article{'s' if article_count != 1 else ''}\n"
        )
        if digest_url:
            message += f"\n<a href=\"{digest_url}\">View digest</a>"

        # Send to all configured users
        bot = Bot(token=self._token)
        try:
            for chat_id in self._chat_ids:
                await bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode="HTML",
                )
            logger.info(f"Digest notification sent to {len(self._chat_ids)} user(s)")
            return True

        except Exception as e:
            logger.warning(f"Failed to send Telegram notification: {e}")
            return False


# Singleton instance
_notifier: TelegramNotifier | None = None


async def get_notifier() -> TelegramNotifier:
    """Get the global notifier instance."""
    global _notifier
    if _notifier is None:
        _notifier = TelegramNotifier()
    return _notifier
