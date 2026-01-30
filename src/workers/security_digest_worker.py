"""
Background worker for Security Digest content ingestion.

This worker runs continuously and:
- Fetches content from due sources at regular intervals
- Handles errors gracefully without crashing
- Supports graceful shutdown on SIGINT/SIGTERM
- Uses jitter to avoid thundering herd problems
- Loads configuration from environment and config files
"""

import asyncio
import logging
import os
import random
import signal
import sys
from dataclasses import dataclass
from typing import NoReturn

from src.core.config.loader import get_config
from src.core.primitives.fetchers.manager import FetcherManager
from src.core.storage.postgres import get_db

logger = logging.getLogger(__name__)

# Global event for graceful shutdown
shutdown_event = asyncio.Event()


@dataclass
class WorkerConfig:
    """Configuration for the worker."""

    interval_seconds: int
    jitter_seconds: int
    max_sources: int
    log_level: str


def load_worker_config() -> WorkerConfig:
    """
    Load worker configuration from environment variables and config files.

    Environment variables take precedence over config files.

    Returns:
        Worker configuration.
    """
    config = get_config()
    worker_config = config.get("workers", {}).get("security_digest_worker", {})

    return WorkerConfig(
        interval_seconds=int(
            os.environ.get(
                "WORKER_INTERVAL_SECONDS",
                worker_config.get("interval_seconds", 300),
            )
        ),
        jitter_seconds=int(
            os.environ.get(
                "WORKER_JITTER_SECONDS",
                worker_config.get("jitter_seconds", 60),
            )
        ),
        max_sources=int(
            os.environ.get(
                "WORKER_MAX_SOURCES",
                worker_config.get("max_sources", 10),
            )
        ),
        log_level=os.environ.get(
            "WORKER_LOG_LEVEL",
            worker_config.get("log_level", "INFO"),
        ),
    )


def setup_logging(log_level: str) -> None:
    """
    Configure logging for the worker.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def handle_signal(signum: int, frame: object) -> None:
    """
    Handle SIGINT/SIGTERM for graceful shutdown.

    Args:
        signum: Signal number.
        frame: Current stack frame.
    """
    signal_name = signal.Signals(signum).name
    logger.info(f"Received signal {signal_name}, shutting down gracefully...")
    shutdown_event.set()


async def run_worker(config: WorkerConfig) -> None:
    """
    Main worker loop.

    Continuously fetches content from due sources with configurable interval and jitter.
    Handles errors gracefully without crashing the worker.

    Args:
        config: Worker configuration.
    """
    logger.info(
        f"Starting worker with interval={config.interval_seconds}s, "
        f"jitter={config.jitter_seconds}s, max_sources={config.max_sources}"
    )

    manager = FetcherManager()

    while not shutdown_event.is_set():
        try:
            logger.info("Starting fetch cycle...")
            stats = await manager.fetch_due_sources(max_sources=config.max_sources)

            logger.info(
                f"Fetch complete: sources_checked={stats.sources_checked}, "
                f"sources_fetched={stats.sources_fetched}, "
                f"articles_found={stats.articles_found}, "
                f"articles_new={stats.articles_new}, "
                f"articles_filtered={stats.articles_filtered}, "
                f"articles_old={stats.articles_old}, "
                f"errors={len(stats.errors)}"
            )

            if stats.errors:
                for error in stats.errors:
                    logger.warning(f"Fetch error: {error}")

        except Exception as e:
            # Log error but don't crash - this is a recoverable error
            logger.error(f"Error in fetch cycle: {e}", exc_info=True)

        # Calculate sleep time with jitter to avoid thundering herd
        jitter = random.uniform(0, config.jitter_seconds)
        sleep_time = config.interval_seconds + jitter

        logger.info(
            f"Sleeping for {sleep_time:.1f}s "
            f"(base={config.interval_seconds}s + jitter={jitter:.1f}s)"
        )

        # Sleep in small chunks to respond quickly to shutdown signal
        sleep_end = asyncio.get_event_loop().time() + sleep_time
        while not shutdown_event.is_set() and asyncio.get_event_loop().time() < sleep_end:
            await asyncio.sleep(1)

    logger.info("Worker stopped")


async def main_async() -> None:
    """
    Async entrypoint for the worker.

    Loads configuration, initializes database connection, and starts the worker loop.
    """
    # Load configuration
    config = load_worker_config()
    setup_logging(config.log_level)

    logger.info("Security Digest Worker starting...")
    logger.info(f"Configuration: {config}")

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Initialize database connection (fatal if fails)
    try:
        db = await get_db()
        await db.connect()
        logger.info("Database connection established")
    except Exception as e:
        logger.critical(f"Cannot connect to database: {e}", exc_info=True)
        sys.exit(1)

    # Run the worker
    try:
        await run_worker(config)
    except KeyboardInterrupt:
        # This should be caught by signal handler, but just in case
        logger.info("Interrupted by user")
    finally:
        # Clean up database connection
        try:
            await db.disconnect()
            logger.info("Database connection closed")
        except Exception as e:
            logger.error(f"Error closing database connection: {e}")


def main() -> NoReturn:
    """
    Main entrypoint for the worker.

    This is the synchronous wrapper that starts the async event loop.
    """
    try:
        asyncio.run(main_async())
    except SystemExit:
        # Re-raise SystemExit to preserve exit code
        raise
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
