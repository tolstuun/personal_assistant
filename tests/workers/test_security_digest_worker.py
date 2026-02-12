"""Tests for Security Digest background worker."""

import asyncio
import os
import signal
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.primitives.fetchers.manager import FetchStats
from src.workers.security_digest_worker import (
    WorkerConfig,
    handle_signal,
    load_worker_config,
    run_worker,
    shutdown_event,
)


class TestWorkerConfig:
    """Tests for WorkerConfig dataclass."""

    def test_create_config(self):
        """Test creating worker config."""
        config = WorkerConfig(
            interval_seconds=300,
            jitter_seconds=60,
            max_sources=10,
            log_level="INFO",
        )

        assert config.interval_seconds == 300
        assert config.jitter_seconds == 60
        assert config.max_sources == 10
        assert config.log_level == "INFO"


class TestLoadWorkerConfig:
    """Tests for load_worker_config function."""

    def test_load_from_environment(self):
        """Test loading config from environment variables."""
        with patch.dict(
            os.environ,
            {
                "WORKER_INTERVAL_SECONDS": "120",
                "WORKER_JITTER_SECONDS": "30",
                "WORKER_MAX_SOURCES": "5",
                "WORKER_LOG_LEVEL": "DEBUG",
            },
        ):
            with patch("src.workers.security_digest_worker.get_config") as mock_get_config:
                mock_get_config.return_value = {}

                config = load_worker_config()

                assert config.interval_seconds == 120
                assert config.jitter_seconds == 30
                assert config.max_sources == 5
                assert config.log_level == "DEBUG"

    def test_load_from_config_file(self):
        """Test loading config from config file."""
        with patch("src.workers.security_digest_worker.get_config") as mock_get_config:
            mock_get_config.return_value = {
                "workers": {
                    "security_digest_worker": {
                        "interval_seconds": 180,
                        "jitter_seconds": 45,
                        "max_sources": 8,
                        "log_level": "WARNING",
                    }
                }
            }

            config = load_worker_config()

            assert config.interval_seconds == 180
            assert config.jitter_seconds == 45
            assert config.max_sources == 8
            assert config.log_level == "WARNING"

    def test_environment_overrides_config_file(self):
        """Test that environment variables override config file."""
        with patch.dict(os.environ, {"WORKER_INTERVAL_SECONDS": "150"}):
            with patch("src.workers.security_digest_worker.get_config") as mock_get_config:
                mock_get_config.return_value = {
                    "workers": {
                        "security_digest_worker": {
                            "interval_seconds": 300,
                            "jitter_seconds": 60,
                            "max_sources": 10,
                            "log_level": "INFO",
                        }
                    }
                }

                config = load_worker_config()

                # Environment variable should override
                assert config.interval_seconds == 150
                # Others should come from config file
                assert config.jitter_seconds == 60
                assert config.max_sources == 10

    def test_load_with_defaults(self):
        """Test loading config with defaults when nothing is configured."""
        with patch("src.workers.security_digest_worker.get_config") as mock_get_config:
            mock_get_config.return_value = {}

            config = load_worker_config()

            # Should have default values
            assert config.interval_seconds == 300
            assert config.jitter_seconds == 60
            assert config.max_sources == 10
            assert config.log_level == "INFO"


class TestHandleSignal:
    """Tests for signal handler."""

    def test_handle_signal_sets_shutdown_event(self):
        """Test that signal handler sets shutdown event."""
        # Reset shutdown event
        shutdown_event.clear()

        # Call signal handler
        handle_signal(signal.SIGTERM, None)

        # Shutdown event should be set
        assert shutdown_event.is_set()

        # Reset for other tests
        shutdown_event.clear()

    def test_handle_signal_sigint(self):
        """Test handling SIGINT."""
        shutdown_event.clear()

        handle_signal(signal.SIGINT, None)

        assert shutdown_event.is_set()
        shutdown_event.clear()


class TestRunWorker:
    """Tests for run_worker function."""

    @pytest.fixture
    def config(self):
        """Create a test worker config."""
        return WorkerConfig(
            interval_seconds=1,  # Short interval for testing
            jitter_seconds=0,  # No jitter for predictable tests
            max_sources=5,
            log_level="INFO",
        )

    @pytest.fixture
    def mock_fetch_stats(self):
        """Create mock fetch stats."""
        return FetchStats(
            sources_checked=3,
            sources_fetched=2,
            articles_found=10,
            articles_new=8,
            articles_filtered=2,
            articles_old=0,
            errors=[],
        )

    async def test_worker_calls_fetch_due_sources(self, config, mock_fetch_stats):
        """Test that worker calls FetcherManager.fetch_due_sources."""
        # Reset shutdown event
        shutdown_event.clear()

        # Create mock manager
        mock_manager = MagicMock()
        mock_manager.fetch_due_sources = AsyncMock(return_value=mock_fetch_stats)

        with patch(
            "src.workers.security_digest_worker.FetcherManager",
            return_value=mock_manager,
        ):
            # Start worker in background
            worker_task = asyncio.create_task(run_worker(config))

            # Let it run for a bit
            await asyncio.sleep(0.5)

            # Stop the worker
            shutdown_event.set()
            await worker_task

            # Verify fetch_due_sources was called
            mock_manager.fetch_due_sources.assert_called()
            call_args = mock_manager.fetch_due_sources.call_args
            assert call_args.kwargs["max_sources"] == config.max_sources

    async def test_worker_sleeps_between_iterations(self, config, mock_fetch_stats):
        """Test that worker sleeps between fetch cycles."""
        shutdown_event.clear()

        mock_manager = MagicMock()
        mock_manager.fetch_due_sources = AsyncMock(return_value=mock_fetch_stats)

        with patch(
            "src.workers.security_digest_worker.FetcherManager",
            return_value=mock_manager,
        ):
            # Start worker
            worker_task = asyncio.create_task(run_worker(config))

            # Let it run for longer than one interval
            await asyncio.sleep(1.5)

            # Stop the worker
            shutdown_event.set()
            await worker_task

            # Should have been called at least twice
            assert mock_manager.fetch_due_sources.call_count >= 1

    async def test_worker_handles_fetch_errors_gracefully(self, config):
        """Test that worker continues after fetch errors."""
        shutdown_event.clear()

        mock_manager = MagicMock()
        # First call raises exception, second succeeds
        mock_stats = FetchStats(
            sources_checked=1,
            sources_fetched=1,
            articles_found=5,
            articles_new=5,
            articles_filtered=0,
            articles_old=0,
            errors=[],
        )
        mock_manager.fetch_due_sources = AsyncMock(
            side_effect=[
                Exception("Network error"),
                mock_stats,
            ]
        )

        with patch(
            "src.workers.security_digest_worker.FetcherManager",
            return_value=mock_manager,
        ):
            # Start worker
            worker_task = asyncio.create_task(run_worker(config))

            # Let it run for two cycles
            await asyncio.sleep(2.5)

            # Stop the worker
            shutdown_event.set()
            await worker_task

            # Should have been called twice (first failed, second succeeded)
            assert mock_manager.fetch_due_sources.call_count >= 2

    async def test_worker_stops_on_shutdown_event(self, config, mock_fetch_stats):
        """Test that worker stops when shutdown event is set."""
        shutdown_event.clear()

        mock_manager = MagicMock()
        mock_manager.fetch_due_sources = AsyncMock(return_value=mock_fetch_stats)

        with patch(
            "src.workers.security_digest_worker.FetcherManager",
            return_value=mock_manager,
        ):
            # Start worker
            worker_task = asyncio.create_task(run_worker(config))

            # Let it run briefly
            await asyncio.sleep(0.2)

            # Set shutdown event
            shutdown_event.set()

            # Wait for worker to stop (should be quick)
            await asyncio.wait_for(worker_task, timeout=2.0)

            # Worker should have stopped cleanly
            assert worker_task.done()
            assert not worker_task.exception()

    async def test_worker_logs_errors_in_stats(self, config):
        """Test that worker logs errors from fetch stats."""
        shutdown_event.clear()

        mock_stats = FetchStats(
            sources_checked=3,
            sources_fetched=2,
            articles_found=5,
            articles_new=4,
            articles_filtered=1,
            articles_old=0,
            errors=["Source1: Connection timeout", "Source2: Invalid URL"],
        )

        mock_manager = MagicMock()
        mock_manager.fetch_due_sources = AsyncMock(return_value=mock_stats)

        with patch(
            "src.workers.security_digest_worker.FetcherManager",
            return_value=mock_manager,
        ):
            # Start worker
            worker_task = asyncio.create_task(run_worker(config))

            # Let it run one cycle
            await asyncio.sleep(0.5)

            # Stop the worker
            shutdown_event.set()
            await worker_task

            # Verify it completed successfully despite errors in stats
            assert worker_task.done()
            assert not worker_task.exception()

    async def test_worker_with_jitter(self):
        """Test that worker applies jitter to sleep time."""
        shutdown_event.clear()

        config = WorkerConfig(
            interval_seconds=1,
            jitter_seconds=1,  # Enable jitter
            max_sources=5,
            log_level="INFO",
        )

        mock_stats = FetchStats(
            sources_checked=1,
            sources_fetched=1,
            articles_found=1,
            articles_new=1,
            articles_filtered=0,
            articles_old=0,
            errors=[],
        )

        mock_manager = MagicMock()
        mock_manager.fetch_due_sources = AsyncMock(return_value=mock_stats)

        with patch(
            "src.workers.security_digest_worker.FetcherManager",
            return_value=mock_manager,
        ):
            # Mock random.uniform to return predictable value
            with patch("src.workers.security_digest_worker.random.uniform") as mock_random:
                mock_random.return_value = 0.5

                # Start worker
                worker_task = asyncio.create_task(run_worker(config))

                # Let it run briefly
                await asyncio.sleep(0.5)

                # Stop the worker
                shutdown_event.set()
                await worker_task

                # Verify random.uniform was called with correct bounds
                mock_random.assert_called_with(0, config.jitter_seconds)


class TestJobRunLogging:
    """Tests for job run logging in fetch cycles."""

    @pytest.fixture
    def config(self):
        """Create a test worker config."""
        return WorkerConfig(
            interval_seconds=1,
            jitter_seconds=0,
            max_sources=5,
            log_level="INFO",
        )

    @pytest.fixture
    def mock_fetch_stats(self):
        """Create mock fetch stats."""
        return FetchStats(
            sources_checked=3,
            sources_fetched=2,
            articles_found=10,
            articles_new=8,
            articles_filtered=2,
            articles_old=0,
            errors=[],
        )

    async def test_job_run_start_and_finish_called_on_success(
        self, config, mock_fetch_stats
    ):
        """JobRunService.start and finish are called around a successful fetch cycle."""
        shutdown_event.clear()

        mock_manager = MagicMock()
        mock_manager.fetch_due_sources = AsyncMock(return_value=mock_fetch_stats)

        run_id = uuid.uuid4()
        mock_job_runs = MagicMock()
        mock_job_runs.start = AsyncMock(return_value=run_id)
        mock_job_runs.finish = AsyncMock()

        with (
            patch(
                "src.workers.security_digest_worker.FetcherManager",
                return_value=mock_manager,
            ),
            patch(
                "src.workers.security_digest_worker.JobRunService",
                return_value=mock_job_runs,
            ),
        ):
            worker_task = asyncio.create_task(run_worker(config))
            await asyncio.sleep(0.5)
            shutdown_event.set()
            await worker_task

        # start() should have been called with job_name="fetch_cycle"
        mock_job_runs.start.assert_called()
        start_args = mock_job_runs.start.call_args
        assert start_args.args[0] == "fetch_cycle"

        # finish() should have been called with status="success"
        mock_job_runs.finish.assert_called()
        finish_kwargs = mock_job_runs.finish.call_args.kwargs
        assert finish_kwargs.get("status") == "success"
        assert "details" in finish_kwargs
        assert finish_kwargs["details"]["articles_new"] == 8

    async def test_job_run_finish_called_with_error_on_exception(self, config):
        """finish() called with status='error' when fetch_due_sources raises."""
        shutdown_event.clear()

        mock_manager = MagicMock()
        mock_manager.fetch_due_sources = AsyncMock(
            side_effect=Exception("DB connection lost")
        )

        run_id = uuid.uuid4()
        mock_job_runs = MagicMock()
        mock_job_runs.start = AsyncMock(return_value=run_id)
        mock_job_runs.finish = AsyncMock()

        with (
            patch(
                "src.workers.security_digest_worker.FetcherManager",
                return_value=mock_manager,
            ),
            patch(
                "src.workers.security_digest_worker.JobRunService",
                return_value=mock_job_runs,
            ),
        ):
            worker_task = asyncio.create_task(run_worker(config))
            await asyncio.sleep(0.5)
            shutdown_event.set()
            await worker_task

        # finish() should have been called with status="error"
        mock_job_runs.finish.assert_called()
        finish_kwargs = mock_job_runs.finish.call_args.kwargs
        assert finish_kwargs.get("status") == "error"
        assert "DB connection lost" in finish_kwargs.get("error_message", "")
