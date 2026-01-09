"""
LLM Router — factory for getting LLM instances.

Reads config and returns appropriate LLM provider.
Supports caching instances for reuse.
"""

import logging
from functools import lru_cache
from typing import Any

from src.core.config.loader import get_config
from src.core.llm.base import BaseLLM, LLMConfig
from src.core.llm.providers.litellm_provider import LiteLLMProvider

logger = logging.getLogger(__name__)

PROVIDERS: dict[str, type[BaseLLM]] = {
    "litellm": LiteLLMProvider,
}


def get_llm(
    model: str | None = None,
    provider: str | None = None,
    **kwargs: Any,
) -> BaseLLM:
    """
    Get an LLM instance.
    
    Args:
        model: Model name (e.g., "claude-sonnet-4-20250514", "gpt-4").
               If None, uses default from config.
        provider: Provider name ("litellm"). If None, uses default.
        **kwargs: Additional config options (temperature, max_tokens, etc.)
    
    Returns:
        BaseLLM instance ready to use
        
    Example:
        llm = get_llm()
        llm = get_llm(model="claude-sonnet-4-20250514")
        llm = get_llm(model="gpt-4", temperature=0.0)
    """
    config = get_config()
    llm_config = config.get("llm", {})
    
    if provider is None:
        provider = llm_config.get("default_provider", "litellm")
    
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}. Available: {list(PROVIDERS.keys())}")
    
    if model is None:
        model = llm_config.get("default_model")
        if model is None:
            raise ValueError("No model specified and no default_model in config")
    
    provider_config = llm_config.get("providers", {}).get(provider, {})
    
    llm_instance_config = LLMConfig(
        model=model,
        temperature=kwargs.get("temperature", provider_config.get("temperature", 0.7)),
        max_tokens=kwargs.get("max_tokens", provider_config.get("max_tokens", 4096)),
        timeout=kwargs.get("timeout", provider_config.get("timeout", 60.0)),
        extra={
            **provider_config.get("extra", {}),
            **{k: v for k, v in kwargs.items() if k not in ("temperature", "max_tokens", "timeout")},
        },
    )
    
    logger.debug(f"Creating LLM: provider={provider}, model={model}")
    
    provider_class = PROVIDERS[provider]
    return provider_class(llm_instance_config)


@lru_cache(maxsize=10)
def get_llm_cached(model: str, provider: str = "litellm") -> BaseLLM:
    """Get a cached LLM instance."""
    return get_llm(model=model, provider=provider)
