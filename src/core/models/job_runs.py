"""
SQLAlchemy model for job run logging.

Stores execution records for background jobs (fetch worker, digest
scheduler, etc.) to provide operational visibility.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.storage.postgres import Base
from src.core.utils.time import utcnow_naive


class JobRun(Base):
    """
    Record of a single background job execution.

    Tracks job name, status (running/success/error/skipped), timing,
    small stats in details, and an optional error message.
    """

    __tablename__ = "job_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow_naive
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_job_runs_job_name", "job_name"),
        Index("ix_job_runs_started_at", "started_at"),
    )

    def __repr__(self) -> str:
        return f"<JobRun(job='{self.job_name}', status='{self.status}')>"
