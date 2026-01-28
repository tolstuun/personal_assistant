"""
FastAPI application — main entry point.

Provides REST API and Telegram webhook endpoint.
Runs with HTTPS using Let's Encrypt certificates.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from telegram import Update

from interfaces.telegram_bot.bot import BotConfig, TelegramBot
from src.core.config import get_config
from src.orchestrator import Orchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global instances
orchestrator: Orchestrator | None = None
telegram_bot: TelegramBot | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown."""
    global orchestrator, telegram_bot

    logger.info("Starting Personal Assistant...")

    # Initialize orchestrator
    orchestrator = Orchestrator()

    # Initialize Telegram bot
    config = get_config()
    bot_config = config.get("telegram", {})

    if not bot_config.get("token"):
        logger.error("Telegram token not found in config!")
        raise ValueError("Telegram token is required. Check config/telegram.yaml")

    telegram_bot = TelegramBot(
        config=BotConfig(
            token=bot_config["token"],
            webhook_url=bot_config["webhook_url"],
            allowed_users=bot_config["allowed_users"],
        ),
        orchestrator=orchestrator
    )

    # Create application and set webhook
    application = telegram_bot.create_application()
    await application.initialize()
    await application.start()

    webhook_url = f"{bot_config['webhook_url']}/telegram/webhook"
    await application.bot.set_webhook(url=webhook_url)
    logger.info(f"Telegram webhook set to: {webhook_url}")

    yield

    # Shutdown
    logger.info("Shutting down...")
    if telegram_bot and telegram_bot.application:
        await telegram_bot.application.stop()
        await telegram_bot.application.shutdown()


app = FastAPI(
    title="Personal Assistant",
    description="Modular AI assistant with atomic components",
    version="0.1.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "personal-assistant"}


@app.get("/status")
async def status():
    """Get system status."""
    if orchestrator:
        return await orchestrator.get_status()
    return {"status": "not initialized"}


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request) -> Response:
    """Handle Telegram webhook updates."""
    if not telegram_bot or not telegram_bot.application:
        return Response(status_code=503)

    try:
        data = await request.json()
        update = Update.de_json(data, telegram_bot.application.bot)
        await telegram_bot.application.process_update(update)
        return Response(status_code=200)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return Response(status_code=500)


@app.post("/api/tasks/{task_type}")
async def execute_task(task_type: str, request: Request):
    """Execute a task via API."""
    if not orchestrator:
        return {"success": False, "error": "Orchestrator not initialized"}

    params = await request.json()
    result = await orchestrator.execute_task(
        task_type=task_type,
        params=params
    )
    return result
