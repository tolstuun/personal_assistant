"""
LLM Router — factory for getting LLM instances.

Reads config and returns appropriate LLM provider.
Supports easy provider switching via config.

Usage:
    # Get default model from current provider
    llm = get_llm()

    # Get a specific tier (fast/smart/smartest)
    llm = get_llm(tier="fast")

    # Get model for a task (uses task_overrides if defined)
    llm = get_llm(task="summarization")

    # Override provider for this call
    llm = get_llm(provider="ollama")

    # Specify exact model (bypasses tier system)
    llm = get_llm(model="gpt-4o-mini")
"""

import logging
from functools import lru_cache
from typing import Any

from src.core.config.loader import get_config
from src.core.llm.base import BaseLLM, LLMConfig
from src.core.llm.providers.litellm_provider import LiteLLMProvider

logger = logging.getLogger(__name__)

# LiteLLM handles all providers through a unified interface
PROVIDERS: dict[str, type[BaseLLM]] = {
    "litellm": LiteLLMProvider,
}

# Map provider names to LiteLLM model prefixes
PROVIDER_PREFIXES: dict[str, str] = {
    "anthropic": "",  # LiteLLM uses model names directly for Anthropic
    "openai": "",     # LiteLLM uses model names directly for OpenAI
    "google": "gemini/",
    "ollama": "ollama/",
}


def _get_llm_config() -> dict[str, Any]:
    """Get LLM config, supporting both old and new formats."""
    config = get_config()
    return config.get("llm", {})


def _resolve_model(
    llm_config: dict[str, Any],
    provider_name: str,
    model: str | None = None,
    tier: str | None = None,
    task: str | None = None,
) -> str:
    """
    Resolve the actual model name to use.

    Priority:
    1. Explicit model parameter (if provided)
    2. Task override -> tier -> model
    3. Tier parameter -> model from provider's models
    4. Provider's default_model
    """
    provider_config = llm_config.get("providers", {}).get(provider_name, {})

    # If explicit model provided, use it
    if model:
        return model

    # If task provided, check task_overrides for a tier
    if task:
        task_overrides = llm_config.get("task_overrides", {})
        tier = task_overrides.get(task, tier)

    # If tier provided (or from task), resolve to model name
    if tier:
        models = provider_config.get("models", {})
        if tier in models:
            return models[tier]
        else:
            logger.warning(f"Tier '{tier}' not found for provider '{provider_name}', using default")

    # Fall back to provider's default model
    default_model = provider_config.get("default_model")
    if default_model:
        return default_model

    # Legacy fallback: check old config format
    legacy_default = llm_config.get("default_model")
    if legacy_default:
        return legacy_default

    raise ValueError(f"No model configured for provider '{provider_name}'")


def _get_api_key(llm_config: dict[str, Any], provider_name: str) -> str | None:
    """Get API key for a provider."""
    provider_config = llm_config.get("providers", {}).get(provider_name, {})
    return provider_config.get("api_key")


def _get_base_url(llm_config: dict[str, Any], provider_name: str) -> str | None:
    """Get base URL for a provider (used by Ollama)."""
    provider_config = llm_config.get("providers", {}).get(provider_name, {})
    return provider_config.get("base_url")


def get_llm(
    model: str | None = None,
    tier: str | None = None,
    task: str | None = None,
    provider: str | None = None,
    **kwargs: Any,
) -> BaseLLM:
    """
    Get an LLM instance.

    Args:
        model: Exact model name (e.g., "claude-sonnet-4-20250514", "gpt-4o").
               Bypasses tier system if provided.
        tier: Model tier ("fast", "smart", "smartest").
              Resolves to provider-specific model.
        task: Task name (e.g., "summarization", "code_review").
              Uses task_overrides to determine tier.
        provider: Provider name ("anthropic", "openai", "google", "ollama").
                  If None, uses current_provider from config.
        **kwargs: Additional config options (temperature, max_tokens, etc.)

    Returns:
        BaseLLM instance ready to use

    Examples:
        llm = get_llm()                      # Default model from current provider
        llm = get_llm(tier="fast")           # Fast model from current provider
        llm = get_llm(task="summarization")  # Model for summarization task
        llm = get_llm(provider="ollama")     # Default model from Ollama
        llm = get_llm(model="gpt-4o-mini")   # Specific model
    """
    llm_config = _get_llm_config()

    # Determine provider
    if provider is None:
        # New format: current_provider
        provider = llm_config.get("current_provider")
        # Legacy fallback: default_provider
        if provider is None:
            provider = llm_config.get("default_provider", "anthropic")

    # Resolve model name
    resolved_model = _resolve_model(llm_config, provider, model, tier, task)

    # Add provider prefix if needed (for LiteLLM)
    prefix = PROVIDER_PREFIXES.get(provider, "")
    if prefix and not resolved_model.startswith(prefix):
        full_model_name = f"{prefix}{resolved_model}"
    else:
        full_model_name = resolved_model

    # Get settings
    settings = llm_config.get("settings", {})

    # Build LLM config
    llm_instance_config = LLMConfig(
        model=full_model_name,
        temperature=kwargs.get("temperature", settings.get("temperature", 0.7)),
        max_tokens=kwargs.get("max_tokens", settings.get("max_tokens", 4096)),
        timeout=kwargs.get("timeout", settings.get("timeout", 60.0)),
        extra={
            **{k: v for k, v in kwargs.items()
               if k not in ("temperature", "max_tokens", "timeout")},
        },
    )

    # Add API key if available
    api_key = _get_api_key(llm_config, provider)
    if api_key:
        llm_instance_config.extra["api_key"] = api_key

    # Add base URL if available (for Ollama)
    base_url = _get_base_url(llm_config, provider)
    if base_url:
        llm_instance_config.extra["api_base"] = base_url

    logger.debug(f"Creating LLM: provider={provider}, model={full_model_name}")

    # Use LiteLLM for all providers
    return LiteLLMProvider(llm_instance_config)


@lru_cache(maxsize=10)
def get_llm_cached(
    model: str | None = None,
    tier: str | None = None,
    provider: str | None = None,
) -> BaseLLM:
    """Get a cached LLM instance."""
    return get_llm(model=model, tier=tier, provider=provider)


def get_current_provider() -> str:
    """Get the name of the currently configured provider."""
    llm_config = _get_llm_config()
    return llm_config.get("current_provider", llm_config.get("default_provider", "anthropic"))


def list_providers() -> list[str]:
    """List all configured providers."""
    llm_config = _get_llm_config()
    return list(llm_config.get("providers", {}).keys())


def list_tiers(provider: str | None = None) -> dict[str, str]:
    """List available tiers and their models for a provider."""
    llm_config = _get_llm_config()
    if provider is None:
        provider = get_current_provider()
    provider_config = llm_config.get("providers", {}).get(provider, {})
    return provider_config.get("models", {})
