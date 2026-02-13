"""Tests for Daily Digest Scheduler worker."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.workers.daily_digest_worker import compute_next_run_utc, run_once


class TestComputeNextRunUtc:
    """Tests for compute_next_run_utc pure function."""

    def test_next_run_today_when_before_digest_time(self) -> None:
        """If current time is before digest_time, next run is today."""
        now = datetime(2026, 2, 12, 6, 0, 0)  # 06:00 UTC
        result = compute_next_run_utc(now, "08:00")
        assert result == datetime(2026, 2, 12, 8, 0, 0)

    def test_next_run_tomorrow_when_after_digest_time(self) -> None:
        """If current time is after digest_time, next run is tomorrow."""
        now = datetime(2026, 2, 12, 10, 0, 0)  # 10:00 UTC
        result = compute_next_run_utc(now, "08:00")
        assert result == datetime(2026, 2, 13, 8, 0, 0)

    def test_next_run_tomorrow_when_exactly_at_digest_time(self) -> None:
        """If current time equals digest_time, next run is tomorrow."""
        now = datetime(2026, 2, 12, 8, 0, 0)
        result = compute_next_run_utc(now, "08:00")
        assert result == datetime(2026, 2, 13, 8, 0, 0)

    def test_midnight_digest_time(self) -> None:
        """Handles 00:00 digest time correctly."""
        now = datetime(2026, 2, 12, 23, 30, 0)
        result = compute_next_run_utc(now, "00:00")
        assert result == datetime(2026, 2, 13, 0, 0, 0)


class TestRunOnce:
    """Tests for run_once scheduler logic."""

    @pytest.fixture
    def mock_digest_service(self):
        """Mock DigestService."""
        service = MagicMock()
        digest = MagicMock()
        digest.id = uuid.uuid4()
        digest.date = "2026-02-12"
        digest.notified_at = datetime(2026, 2, 12, 8, 5, 0)
        service.generate = AsyncMock(return_value=digest)
        return service

    @pytest.fixture
    def mock_job_runs(self):
        """Mock JobRunService."""
        service = MagicMock()
        service.start = AsyncMock(return_value=uuid.uuid4())
        service.finish = AsyncMock()
        return service

    @pytest.fixture
    def mock_settings(self):
        """Mock SettingsService."""
        service = MagicMock()

        async def mock_get(key):
            defaults = {
                "digest_time": "08:00",
                "telegram_notifications": True,
            }
            return defaults[key]

        service.get = AsyncMock(side_effect=mock_get)
        return service

    async def test_generates_digest_when_none_exists(
        self, mock_digest_service, mock_job_runs, mock_settings
    ) -> None:
        """When no digest exists for today, generates one and records success."""
        now = datetime(2026, 2, 12, 8, 0, 0)

        with patch(
            "src.workers.daily_digest_worker._digest_exists_for_date",
            new_callable=AsyncMock,
            return_value=False,
        ):
            await run_once(
                now_utc=now,
                digest_service=mock_digest_service,
                job_runs=mock_job_runs,
                settings_service=mock_settings,
            )

        mock_job_runs.start.assert_called_once()
        mock_digest_service.generate.assert_called_once()
        mock_job_runs.finish.assert_called_once()
        finish_kwargs = mock_job_runs.finish.call_args.kwargs
        assert finish_kwargs["status"] == "success"
        assert finish_kwargs["details"]["notified"] is True

    async def test_skips_when_digest_already_exists(
        self, mock_digest_service, mock_job_runs, mock_settings
    ) -> None:
        """When digest already exists for today, skips and records skipped."""
        now = datetime(2026, 2, 12, 8, 0, 0)

        with patch(
            "src.workers.daily_digest_worker._digest_exists_for_date",
            new_callable=AsyncMock,
            return_value=True,
        ):
            await run_once(
                now_utc=now,
                digest_service=mock_digest_service,
                job_runs=mock_job_runs,
                settings_service=mock_settings,
            )

        mock_digest_service.generate.assert_not_called()
        mock_job_runs.finish.assert_called_once()
        finish_kwargs = mock_job_runs.finish.call_args.kwargs
        assert finish_kwargs["status"] == "skipped"
        assert finish_kwargs["details"]["reason"] == "already_exists"

    async def test_records_error_when_generation_fails(
        self, mock_digest_service, mock_job_runs, mock_settings
    ) -> None:
        """When digest generation raises, records error and does not crash."""
        now = datetime(2026, 2, 12, 8, 0, 0)
        mock_digest_service.generate = AsyncMock(
            side_effect=Exception("LLM timeout")
        )

        with patch(
            "src.workers.daily_digest_worker._digest_exists_for_date",
            new_callable=AsyncMock,
            return_value=False,
        ):
            await run_once(
                now_utc=now,
                digest_service=mock_digest_service,
                job_runs=mock_job_runs,
                settings_service=mock_settings,
            )

        mock_job_runs.finish.assert_called_once()
        finish_kwargs = mock_job_runs.finish.call_args.kwargs
        assert finish_kwargs["status"] == "error"
        assert "LLM timeout" in finish_kwargs["error_message"]
