"""
Tests for TelegramNotifier.

Unit tests that mock the telegram.Bot to avoid real API calls.
"""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.models.security_digest import Digest, DigestStatus
from src.core.services.notifier import TelegramNotifier


def _make_digest(
    digest_date: date | None = None,
    html_path: str = "data/digests/digest-2026-02-05.html",
) -> MagicMock:
    """Create a mock Digest for testing."""
    digest = MagicMock(spec=Digest)
    digest.id = uuid.uuid4()
    digest.date = digest_date or date(2026, 2, 5)
    digest.status = DigestStatus.READY
    digest.html_path = html_path
    return digest


class TestTelegramNotifierSend:
    """Tests for TelegramNotifier.send_digest_notification()."""

    @pytest.mark.asyncio
    async def test_send_returns_true_on_success(self) -> None:
        """Returns True when message is sent successfully."""
        notifier = TelegramNotifier(
            token="fake-token",
            chat_ids=[123],
            base_url="https://example.com",
        )

        mock_bot = AsyncMock()
        with patch("src.core.services.notifier.Bot", return_value=mock_bot):
            result = await notifier.send_digest_notification(
                digest=_make_digest(),
                article_count=10,
            )

        assert result is True
        mock_bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_returns_false_on_error(self) -> None:
        """Returns False when telegram API raises an exception."""
        notifier = TelegramNotifier(
            token="fake-token",
            chat_ids=[123],
            base_url="https://example.com",
        )

        mock_bot = AsyncMock()
        mock_bot.send_message.side_effect = RuntimeError("API error")
        with patch("src.core.services.notifier.Bot", return_value=mock_bot):
            result = await notifier.send_digest_notification(
                digest=_make_digest(),
                article_count=10,
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_send_returns_false_without_token(self) -> None:
        """Returns False when token is empty."""
        notifier = TelegramNotifier(token="", chat_ids=[123], base_url="https://example.com")

        result = await notifier.send_digest_notification(
            digest=_make_digest(),
            article_count=5,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_send_returns_false_without_chat_ids(self) -> None:
        """Returns False when no chat IDs are configured."""
        notifier = TelegramNotifier(
            token="fake-token", chat_ids=[], base_url="https://example.com"
        )

        result = await notifier.send_digest_notification(
            digest=_make_digest(),
            article_count=5,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_contains_date(self) -> None:
        """Message includes the digest date."""
        notifier = TelegramNotifier(
            token="fake-token",
            chat_ids=[123],
            base_url="https://example.com",
        )

        mock_bot = AsyncMock()
        with patch("src.core.services.notifier.Bot", return_value=mock_bot):
            await notifier.send_digest_notification(
                digest=_make_digest(digest_date=date(2026, 2, 5)),
                article_count=10,
            )

        call_args = mock_bot.send_message.call_args
        message = call_args.kwargs["text"]
        assert "2026-02-05" in message

    @pytest.mark.asyncio
    async def test_send_message_contains_article_count(self) -> None:
        """Message includes the article count."""
        notifier = TelegramNotifier(
            token="fake-token",
            chat_ids=[123],
            base_url="https://example.com",
        )

        mock_bot = AsyncMock()
        with patch("src.core.services.notifier.Bot", return_value=mock_bot):
            await notifier.send_digest_notification(
                digest=_make_digest(),
                article_count=15,
            )

        call_args = mock_bot.send_message.call_args
        message = call_args.kwargs["text"]
        assert "15 articles" in message

    @pytest.mark.asyncio
    async def test_send_message_contains_digest_link(self) -> None:
        """Message includes a link to the digest HTML."""
        notifier = TelegramNotifier(
            token="fake-token",
            chat_ids=[123],
            base_url="https://example.com",
        )

        mock_bot = AsyncMock()
        with patch("src.core.services.notifier.Bot", return_value=mock_bot):
            await notifier.send_digest_notification(
                digest=_make_digest(html_path="data/digests/digest-2026-02-05.html"),
                article_count=10,
            )

        call_args = mock_bot.send_message.call_args
        message = call_args.kwargs["text"]
        assert "https://example.com/digests/digest-2026-02-05.html" in message

    @pytest.mark.asyncio
    async def test_send_to_multiple_users(self) -> None:
        """Sends message to all configured chat IDs."""
        notifier = TelegramNotifier(
            token="fake-token",
            chat_ids=[111, 222, 333],
            base_url="https://example.com",
        )

        mock_bot = AsyncMock()
        with patch("src.core.services.notifier.Bot", return_value=mock_bot):
            result = await notifier.send_digest_notification(
                digest=_make_digest(),
                article_count=10,
            )

        assert result is True
        assert mock_bot.send_message.call_count == 3
        sent_chat_ids = [call.kwargs["chat_id"] for call in mock_bot.send_message.call_args_list]
        assert sent_chat_ids == [111, 222, 333]

    @pytest.mark.asyncio
    async def test_send_uses_html_parse_mode(self) -> None:
        """Message is sent with HTML parse mode."""
        notifier = TelegramNotifier(
            token="fake-token",
            chat_ids=[123],
            base_url="https://example.com",
        )

        mock_bot = AsyncMock()
        with patch("src.core.services.notifier.Bot", return_value=mock_bot):
            await notifier.send_digest_notification(
                digest=_make_digest(),
                article_count=10,
            )

        call_args = mock_bot.send_message.call_args
        assert call_args.kwargs["parse_mode"] == "HTML"
