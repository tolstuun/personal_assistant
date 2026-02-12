"""
Service for recording background job executions.

Provides start/finish/get_latest methods for tracking when jobs run,
whether they succeed or fail, and how long they take.
"""

import logging
import uuid
from typing import Any

from sqlalchemy import select

from src.core.models.job_runs import JobRun
from src.core.storage.postgres import Database, get_db
from src.core.utils.time import utcnow_naive

logger = logging.getLogger(__name__)


class JobRunService:
    """
    Service for logging background job runs.

    Records each execution with status, timing, and optional details/errors.
    """

    def __init__(self, db: Database | None = None) -> None:
        """Initialize with a database instance, or None to use get_db() lazily."""
        self._db = db

    async def _get_db(self) -> Database:
        """Get the database instance, resolving lazily if needed."""
        if self._db is None:
            self._db = await get_db()
        return self._db

    async def start(self, job_name: str, details: dict[str, Any] | None = None) -> uuid.UUID:
        """
        Record the start of a job run.

        Creates a row with status="running" and returns the run ID.

        Args:
            job_name: Name of the job (e.g. "security_digest_worker").
            details: Optional initial metadata dict.

        Returns:
            The UUID of the new run record.
        """
        run = JobRun(
            job_name=job_name,
            status="running",
            started_at=utcnow_naive(),
            details=details if details is not None else {},
        )
        db = await self._get_db()
        async with db.session() as session:
            session.add(run)
            await session.commit()
            await session.refresh(run)

        logger.info(f"Job run started: {job_name} ({run.id})")
        return run.id

    async def finish(
        self,
        run_id: uuid.UUID,
        status: str,
        details: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> None:
        """
        Record the completion of a job run.

        Sets the final status, finished_at timestamp, and optional
        details/error message.

        Args:
            run_id: The UUID returned by start().
            status: Final status (success, error, or skipped).
            details: Optional metadata dict (replaces existing details if provided).
            error_message: Optional short error description.
        """
        db = await self._get_db()
        async with db.session() as session:
            stmt = select(JobRun).where(JobRun.id == run_id)
            result = await session.execute(stmt)
            run = result.scalar_one_or_none()

            if run is None:
                logger.warning(f"Job run not found: {run_id}")
                return

            run.status = status
            run.finished_at = utcnow_naive()
            if details is not None:
                run.details = details
            if error_message is not None:
                run.error_message = error_message

            await session.commit()

        logger.info(f"Job run finished: {run.job_name} ({run_id}) -> {status}")

    async def get_latest(self, job_name: str) -> JobRun | None:
        """
        Get the most recent run for a job.

        Args:
            job_name: Name of the job.

        Returns:
            The most recent JobRun, or None if no runs exist.
        """
        db = await self._get_db()
        async with db.session() as session:
            stmt = (
                select(JobRun)
                .where(JobRun.job_name == job_name)
                .order_by(JobRun.started_at.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
