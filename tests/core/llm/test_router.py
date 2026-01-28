"""
Tests for LLM router configuration and model resolution.

These tests verify the config parsing and model resolution logic
without making actual API calls.
"""

import pytest
from unittest.mock import patch

from src.core.llm.router import (
    _resolve_model,
    _get_api_key,
    _get_base_url,
    get_current_provider,
    list_providers,
    list_tiers,
    get_llm,
)


# Sample config matching new format
SAMPLE_CONFIG = {
    "llm": {
        "current_provider": "anthropic",
        "providers": {
            "anthropic": {
                "api_key": "sk-ant-test",
                "default_model": "claude-sonnet-4-20250514",
                "models": {
                    "fast": "claude-haiku-3-5-20241022",
                    "smart": "claude-sonnet-4-20250514",
                    "smartest": "claude-opus-4-20250514",
                },
            },
            "openai": {
                "api_key": "sk-openai-test",
                "default_model": "gpt-4o",
                "models": {
                    "fast": "gpt-4o-mini",
                    "smart": "gpt-4o",
                    "smartest": "gpt-4o",
                },
            },
            "ollama": {
                "base_url": "http://localhost:11434",
                "default_model": "llama3",
                "models": {
                    "fast": "llama3",
                    "smart": "llama3:70b",
                    "smartest": "llama3:70b",
                },
            },
        },
        "settings": {
            "temperature": 0.7,
            "max_tokens": 4096,
            "timeout": 60.0,
        },
        "task_overrides": {
            "summarization": "fast",
            "code_review": "smartest",
        },
    }
}


@pytest.fixture
def mock_config():
    """Mock get_config to return sample config."""
    with patch("src.core.llm.router.get_config") as mock:
        mock.return_value = SAMPLE_CONFIG
        yield mock


class TestResolveModel:
    """Tests for _resolve_model function."""

    def test_explicit_model_takes_priority(self):
        """Explicit model parameter should be used as-is."""
        llm_config = SAMPLE_CONFIG["llm"]
        result = _resolve_model(llm_config, "anthropic", model="custom-model")
        assert result == "custom-model"

    def test_tier_resolves_to_provider_model(self):
        """Tier should resolve to the provider's model."""
        llm_config = SAMPLE_CONFIG["llm"]

        result = _resolve_model(llm_config, "anthropic", tier="fast")
        assert result == "claude-haiku-3-5-20241022"

        result = _resolve_model(llm_config, "openai", tier="fast")
        assert result == "gpt-4o-mini"

    def test_task_resolves_via_task_overrides(self):
        """Task should resolve through task_overrides to tier to model."""
        llm_config = SAMPLE_CONFIG["llm"]

        # summarization -> fast -> claude-haiku
        result = _resolve_model(llm_config, "anthropic", task="summarization")
        assert result == "claude-haiku-3-5-20241022"

        # code_review -> smartest -> claude-opus
        result = _resolve_model(llm_config, "anthropic", task="code_review")
        assert result == "claude-opus-4-20250514"

    def test_unknown_task_falls_back_to_default(self):
        """Unknown task should fall back to provider's default_model."""
        llm_config = SAMPLE_CONFIG["llm"]
        result = _resolve_model(llm_config, "anthropic", task="unknown_task")
        assert result == "claude-sonnet-4-20250514"

    def test_no_args_returns_default_model(self):
        """No arguments should return provider's default_model."""
        llm_config = SAMPLE_CONFIG["llm"]
        result = _resolve_model(llm_config, "anthropic")
        assert result == "claude-sonnet-4-20250514"


class TestGetApiKey:
    """Tests for _get_api_key function."""

    def test_returns_api_key_for_provider(self):
        """Should return the API key for the specified provider."""
        llm_config = SAMPLE_CONFIG["llm"]
        assert _get_api_key(llm_config, "anthropic") == "sk-ant-test"
        assert _get_api_key(llm_config, "openai") == "sk-openai-test"

    def test_returns_none_for_provider_without_key(self):
        """Should return None for providers without API key (like Ollama)."""
        llm_config = SAMPLE_CONFIG["llm"]
        assert _get_api_key(llm_config, "ollama") is None


class TestGetBaseUrl:
    """Tests for _get_base_url function."""

    def test_returns_base_url_for_ollama(self):
        """Should return base_url for Ollama."""
        llm_config = SAMPLE_CONFIG["llm"]
        assert _get_base_url(llm_config, "ollama") == "http://localhost:11434"

    def test_returns_none_for_cloud_providers(self):
        """Should return None for cloud providers."""
        llm_config = SAMPLE_CONFIG["llm"]
        assert _get_base_url(llm_config, "anthropic") is None


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_get_current_provider(self, mock_config):
        """Should return current_provider from config."""
        assert get_current_provider() == "anthropic"

    def test_list_providers(self, mock_config):
        """Should list all configured providers."""
        providers = list_providers()
        assert "anthropic" in providers
        assert "openai" in providers
        assert "ollama" in providers

    def test_list_tiers(self, mock_config):
        """Should list tiers for current provider."""
        tiers = list_tiers()
        assert tiers == {
            "fast": "claude-haiku-3-5-20241022",
            "smart": "claude-sonnet-4-20250514",
            "smartest": "claude-opus-4-20250514",
        }

    def test_list_tiers_for_specific_provider(self, mock_config):
        """Should list tiers for specified provider."""
        tiers = list_tiers(provider="openai")
        assert tiers == {
            "fast": "gpt-4o-mini",
            "smart": "gpt-4o",
            "smartest": "gpt-4o",
        }


class TestGetLlm:
    """Tests for get_llm function."""

    def test_get_llm_returns_provider_instance(self, mock_config):
        """get_llm should return a valid LLM instance."""
        llm = get_llm()
        assert llm is not None
        assert llm.get_model_name() == "claude-sonnet-4-20250514"

    def test_get_llm_with_tier(self, mock_config):
        """get_llm with tier should resolve to correct model."""
        llm = get_llm(tier="fast")
        assert llm.get_model_name() == "claude-haiku-3-5-20241022"

    def test_get_llm_with_provider_override(self, mock_config):
        """get_llm with provider should use that provider."""
        llm = get_llm(provider="openai")
        assert llm.get_model_name() == "gpt-4o"

    def test_get_llm_with_ollama_adds_prefix(self, mock_config):
        """Ollama models should get ollama/ prefix."""
        llm = get_llm(provider="ollama")
        assert llm.get_model_name() == "ollama/llama3"

    def test_get_llm_with_task(self, mock_config):
        """get_llm with task should use task_overrides."""
        llm = get_llm(task="summarization")
        # summarization -> fast -> claude-haiku
        assert llm.get_model_name() == "claude-haiku-3-5-20241022"


class TestBackwardsCompatibility:
    """Tests for backwards compatibility with old config format."""

    def test_legacy_default_provider(self):
        """Should fall back to default_provider if current_provider not set."""
        legacy_config = {
            "llm": {
                "default_provider": "litellm",
                "default_model": "gpt-4",
            }
        }
        with patch("src.core.llm.router.get_config") as mock:
            mock.return_value = legacy_config
            provider = get_current_provider()
            assert provider == "litellm"
