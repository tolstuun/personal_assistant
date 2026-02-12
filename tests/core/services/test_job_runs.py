"""
Tests for JobRunService.

Integration tests that require a running PostgreSQL instance.
Run: pytest tests/core/services/test_job_runs.py -v
"""

import uuid

import pytest
import pytest_asyncio

from tests.core.primitives.fetchers.conftest import (
    clean_database,  # noqa: F401
    database,  # noqa: F401
    database_config,  # noqa: F401
)


@pytest_asyncio.fixture
async def job_run_service(clean_database):  # noqa: F811
    """Provide a JobRunService backed by the test database."""
    from src.core.services.job_runs import JobRunService

    return JobRunService(clean_database)


@pytest.mark.asyncio
async def test_start_creates_running_job_run(job_run_service) -> None:
    """start() creates a JobRun with status='running' and non-null started_at."""
    run_id = await job_run_service.start("test_worker")

    assert isinstance(run_id, uuid.UUID)

    run = await job_run_service.get_latest("test_worker")
    assert run is not None
    assert run.job_name == "test_worker"
    assert run.status == "running"
    assert run.started_at is not None
    assert run.finished_at is None
    assert run.error_message is None
    assert run.details == {}


@pytest.mark.asyncio
async def test_finish_updates_status_and_fields(job_run_service) -> None:
    """finish() updates status, sets finished_at, writes error_message and details."""
    run_id = await job_run_service.start("test_worker")

    await job_run_service.finish(
        run_id,
        status="error",
        details={"sources_fetched": 3},
        error_message="Connection timeout",
    )

    run = await job_run_service.get_latest("test_worker")
    assert run is not None
    assert run.status == "error"
    assert run.finished_at is not None
    assert run.finished_at >= run.started_at
    assert run.error_message == "Connection timeout"
    assert run.details == {"sources_fetched": 3}


@pytest.mark.asyncio
async def test_get_latest_returns_newest_by_started_at(job_run_service) -> None:
    """get_latest() returns the most recent run ordered by started_at."""
    # Create two runs
    run_id_1 = await job_run_service.start("test_worker")
    await job_run_service.finish(run_id_1, status="success")

    run_id_2 = await job_run_service.start("test_worker")
    await job_run_service.finish(run_id_2, status="error", error_message="fail")

    latest = await job_run_service.get_latest("test_worker")
    assert latest is not None
    assert latest.id == run_id_2
    assert latest.status == "error"


@pytest.mark.asyncio
async def test_get_latest_returns_none_when_no_runs(job_run_service) -> None:
    """get_latest() returns None when no runs exist for a job_name."""
    result = await job_run_service.get_latest("nonexistent_worker")
    assert result is None
