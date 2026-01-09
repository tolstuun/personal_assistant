"""
Telegram bot interface.

Receives commands from Telegram and routes them to the orchestrator.
Uses webhook mode for production deployment.
"""

import logging
from dataclasses import dataclass
from typing import Any

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.core.config import get_config
from src.orchestrator import Orchestrator

logger = logging.getLogger(__name__)


@dataclass
class BotConfig:
    """Telegram bot configuration."""
    token: str
    webhook_url: str
    allowed_users: list[int]
    webhook_path: str = "/telegram/webhook"


class TelegramBot:
    """
    Telegram bot that interfaces with the orchestrator.
    
    Usage:
        bot = TelegramBot(config, orchestrator)
        application = bot.create_application()
        
        # For webhook mode, integrate with FastAPI
    """
    
    def __init__(self, config: BotConfig, orchestrator: Orchestrator):
        self.config = config
        self.orchestrator = orchestrator
        self.application: Application | None = None
    
    def create_application(self) -> Application:
        """Create and configure the Telegram application."""
        self.application = (
            Application.builder()
            .token(self.config.token)
            .build()
        )
        
        # Add handlers
        self.application.add_handler(CommandHandler("start", self._cmd_start))
        self.application.add_handler(CommandHandler("help", self._cmd_help))
        self.application.add_handler(CommandHandler("fetch", self._cmd_fetch))
        self.application.add_handler(CommandHandler("status", self._cmd_status))
        
        # Handle unknown commands
        self.application.add_handler(
            MessageHandler(filters.COMMAND, self._unknown_command)
        )
        
        # Handle regular messages
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )
        
        return self.application
    
    def _is_authorized(self, user_id: int) -> bool:
        """Check if user is allowed to use the bot."""
        return user_id in self.config.allowed_users
    
    async def _check_auth(self, update: Update) -> bool:
        """Check authorization and send error if not authorized."""
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            logger.warning(f"Unauthorized access attempt from user {user_id}")
            await update.message.reply_text(
                "⛔ Access denied. You are not authorized to use this bot."
            )
            return False
        return True
    
    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        if not await self._check_auth(update):
            return
        
        await update.message.reply_text(
            "👋 Welcome to Personal Assistant!\n\n"
            "Available commands:\n"
            "/fetch <url> — Fetch content from URL\n"
            "/status — Check system status\n"
            "/help — Show this help"
        )
    
    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        if not await self._check_auth(update):
            return
        
        await update.message.reply_text(
            "📖 *Personal Assistant Help*\n\n"
            "*Commands:*\n"
            "/fetch <url> — Fetch and analyze URL content\n"
            "/status — System status\n"
            "/help — This message\n\n"
            "*Coming soon:*\n"
            "• Security digest\n"
            "• Job hunter\n"
            "• Code assistant",
            parse_mode="Markdown"
        )
    
    async def _cmd_fetch(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /fetch command."""
        if not await self._check_auth(update):
            return
        
        if not context.args:
            await update.message.reply_text(
                "❌ Usage: /fetch <url>\n"
                "Example: /fetch https://example.com"
            )
            return
        
        url = context.args[0]
        
        # Send "processing" message
        processing_msg = await update.message.reply_text(
            f"🔄 Fetching {url}..."
        )
        
        try:
            # Route to orchestrator
            result = await self.orchestrator.execute_task(
                task_type="fetch",
                params={"url": url},
                user_id=update.effective_user.id
            )
            
            if result["success"]:
                data = result["data"]
                response = (
                    f"✅ *Fetch successful*\n\n"
                    f"*URL:* {data['url']}\n"
                    f"*Status:* {data['status_code']}\n"
                    f"*Type:* {data['content_type']}\n"
                    f"*Size:* {data['content_length']} bytes\n"
                    f"*Time:* {data['elapsed_ms']}ms"
                )
            else:
                response = f"❌ *Fetch failed*\n\n{result['error']}"
            
            await processing_msg.edit_text(response, parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"Fetch command failed: {e}")
            await processing_msg.edit_text(f"❌ Error: {str(e)}")
    
    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        if not await self._check_auth(update):
            return
        
        status = await self.orchestrator.get_status()
        
        await update.message.reply_text(
            f"📊 *System Status*\n\n"
            f"*Orchestrator:* {status['orchestrator']}\n"
            f"*Agents:* {status['agents_count']}\n"
            f"*Tasks processed:* {status['tasks_processed']}",
            parse_mode="Markdown"
        )
    
    async def _unknown_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle unknown commands."""
        if not await self._check_auth(update):
            return
        
        await update.message.reply_text(
            "❓ Unknown command. Use /help to see available commands."
        )
    
    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular text messages."""
        if not await self._check_auth(update):
            return
        
        # For now, just acknowledge
        await update.message.reply_text(
            "💬 I received your message. "
            "For now, please use commands (start with /). "
            "Natural language processing coming soon!"
        )


def create_bot_from_config(orchestrator: Orchestrator) -> TelegramBot:
    """Create bot instance from config file."""
    config = get_config()
    bot_config = config.get("telegram", {})
    
    return TelegramBot(
        config=BotConfig(
            token=bot_config["token"],
            webhook_url=bot_config["webhook_url"],
            allowed_users=bot_config["allowed_users"],
        ),
        orchestrator=orchestrator
    )
