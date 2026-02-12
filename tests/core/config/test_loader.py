"""Tests for config loader workers.yaml support."""

from pathlib import Path

import pytest

from src.core.config.loader import get_config


@pytest.fixture(autouse=True)
def _clear_config_cache() -> None:
    """Clear lru_cache before and after each test."""
    get_config.cache_clear()
    yield
    get_config.cache_clear()


@pytest.fixture()
def tmp_config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory with a workers example file."""
    workers_example = tmp_path / "workers.example.yaml"
    workers_example.write_text(
        "workers:\n"
        "  security_digest_worker:\n"
        "    interval_seconds: 300\n"
        "    jitter_seconds: 60\n"
        "    max_sources: 10\n"
        "    log_level: INFO\n"
    )
    return tmp_path


def test_workers_config_loaded(tmp_config_dir: Path) -> None:
    """get_config should include 'workers' key when workers.example.yaml exists."""
    config = get_config(config_dir=str(tmp_config_dir))

    assert "workers" in config
    worker_cfg = config["workers"]["security_digest_worker"]
    assert worker_cfg["interval_seconds"] == 300
    assert worker_cfg["jitter_seconds"] == 60
    assert worker_cfg["max_sources"] == 10
    assert worker_cfg["log_level"] == "INFO"


def test_workers_yaml_overrides_example(tmp_config_dir: Path) -> None:
    """workers.yaml should deep-merge over workers.example.yaml."""
    # Add a workers.yaml that overrides interval and adds a new key
    workers_override = tmp_config_dir / "workers.yaml"
    workers_override.write_text(
        "workers:\n"
        "  security_digest_worker:\n"
        "    interval_seconds: 120\n"
    )

    config = get_config(config_dir=str(tmp_config_dir))

    worker_cfg = config["workers"]["security_digest_worker"]
    # Overridden value
    assert worker_cfg["interval_seconds"] == 120
    # Values from example that were NOT overridden should survive
    assert worker_cfg["jitter_seconds"] == 60
    assert worker_cfg["max_sources"] == 10
    assert worker_cfg["log_level"] == "INFO"
