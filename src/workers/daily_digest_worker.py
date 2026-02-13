"""
Background worker for scheduled daily digest generation.

This worker runs continuously and:
- Reads the digest_time setting (interpreted as UTC, e.g. "08:00")
- Sleeps until the next scheduled run time
- Generates a digest via DigestService if one doesn't already exist for today
- Records each attempt as a job_run with status success/skipped/error
- Supports graceful shutdown on SIGINT/SIGTERM
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime, timedelta
from typing import NoReturn

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from src.core.models.security_digest import Digest
from src.core.services.digest import DigestService
from src.core.services.job_runs import JobRunService
from src.core.services.settings import SettingsService
from src.core.storage.postgres import get_db
from src.core.utils.time import utcnow_naive

logger = logging.getLogger(__name__)

# Global event for graceful shutdown
shutdown_event = asyncio.Event()


def compute_next_run_utc(now_utc: datetime, digest_time_str: str) -> datetime:
    """
    Calculate the next run time in UTC.

    If the digest time hasn't passed today, returns today at digest_time.
    Otherwise returns tomorrow at digest_time.

    Args:
        now_utc: Current UTC time.
        digest_time_str: Time string in HH:MM format.

    Returns:
        Next run datetime in UTC.
    """
    hour, minute = map(int, digest_time_str.split(":"))
    target_today = now_utc.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if now_utc < target_today:
        return target_today
    return target_today + timedelta(days=1)


async def _digest_exists_for_date(target_date: datetime) -> bool:
    """
    Check if a digest already exists for the given date.

    Args:
        target_date: The date to check (only date part is used).

    Returns:
        True if a digest exists for that date.
    """
    db = await get_db()
    async with db.session() as session:
        stmt = select(func.count()).select_from(Digest).where(
            Digest.date == target_date.date()
        )
        result = await session.execute(stmt)
        return result.scalar_one() > 0


async def run_once(
    now_utc: datetime,
    digest_service: DigestService,
    job_runs: JobRunService,
    settings_service: SettingsService,
) -> None:
    """
    Execute a single digest generation attempt.

    Checks if a digest already exists for today, generates one if not,
    and records the outcome as a job run.

    Args:
        now_utc: Current UTC time.
        digest_service: Service for generating digests.
        job_runs: Service for recording job runs.
        settings_service: Service for reading settings.
    """
    digest_date = now_utc.date()
    digest_time_str = await settings_service.get("digest_time")

    # Start job run
    run_id = await job_runs.start(
        "digest_scheduler",
        details={"digest_date": str(digest_date), "digest_time_utc": digest_time_str},
    )

    # Check if digest already exists
    if await _digest_exists_for_date(now_utc):
        logger.info(f"Digest already exists for {digest_date}, skipping")
        await job_runs.finish(
            run_id,
            status="skipped",
            details={
                "digest_date": str(digest_date),
                "reason": "already_exists",
            },
        )
        return

    # Generate digest
    try:
        digest = await digest_service.generate()

        notified = digest.notified_at is not None

        logger.info(
            f"Digest generated for {digest_date}: "
            f"id={digest.id}, notified={notified}"
        )

        await job_runs.finish(
            run_id,
            status="success",
            details={
                "digest_date": str(digest_date),
                "digest_id": str(digest.id),
                "notified": notified,
                "digest_time_utc": digest_time_str,
            },
        )

    except IntegrityError:
        # Race condition: another process created the digest between our check
        # and our insert
        logger.info(f"Digest unique conflict for {digest_date}, skipping")
        await job_runs.finish(
            run_id,
            status="skipped",
            details={
                "digest_date": str(digest_date),
                "reason": "unique_conflict",
            },
        )

    except Exception as e:
        logger.error(f"Digest generation failed: {e}", exc_info=True)
        await job_runs.finish(
            run_id,
            status="error",
            error_message=str(e)[:500],
            details={
                "digest_date": str(digest_date),
                "digest_time_utc": digest_time_str,
            },
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


async def scheduler_loop() -> None:
    """
    Main scheduler loop.

    Reads digest_time from settings, computes the next run,
    sleeps until then, and calls run_once.
    """
    settings_service = SettingsService()
    digest_service = DigestService()
    job_runs = JobRunService()

    while not shutdown_event.is_set():
        # Read digest_time from settings
        try:
            digest_time_str = await settings_service.get("digest_time")
        except Exception as e:
            logger.warning(f"Could not read digest_time setting: {e}, defaulting to 08:00")
            digest_time_str = "08:00"

        now = utcnow_naive()
        next_run = compute_next_run_utc(now, digest_time_str)
        sleep_seconds = (next_run - now).total_seconds()

        logger.info(
            f"Next digest run at {next_run.strftime('%Y-%m-%d %H:%M')} UTC "
            f"(sleeping {sleep_seconds:.0f}s)"
        )

        # Sleep in small chunks to respond quickly to shutdown signal
        sleep_end = asyncio.get_event_loop().time() + sleep_seconds
        while not shutdown_event.is_set() and asyncio.get_event_loop().time() < sleep_end:
            await asyncio.sleep(1)

        if shutdown_event.is_set():
            break

        # Run the digest generation
        now = utcnow_naive()
        try:
            await run_once(
                now_utc=now,
                digest_service=digest_service,
                job_runs=job_runs,
                settings_service=settings_service,
            )
        except Exception as e:
            logger.error(f"Unexpected error in scheduler: {e}", exc_info=True)

    logger.info("Digest scheduler stopped")


async def main_async() -> None:
    """
    Async entrypoint for the digest scheduler.

    Initializes database connection and starts the scheduler loop.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.info("Daily Digest Scheduler starting...")

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

    # Run the scheduler
    try:
        await scheduler_loop()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        try:
            await db.disconnect()
            logger.info("Database connection closed")
        except Exception as e:
            logger.error(f"Error closing database connection: {e}")


def main() -> NoReturn:
    """
    Main entrypoint for the digest scheduler.

    This is the synchronous wrapper that starts the async event loop.
    """
    try:
        asyncio.run(main_async())
    except SystemExit:
        raise
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
