"""
LLM module — unified interface to language models.

Usage:
    from src.core.llm import get_llm

    # Get default model from current provider
    llm = get_llm()
    response = await llm.complete("Hello!")

    # Get a specific tier (fast/smart/smartest)
    llm = get_llm(tier="fast")

    # Get model for a task
    llm = get_llm(task="summarization")

    # Switch provider for this call
    llm = get_llm(provider="ollama")
"""

from src.core.llm.base import BaseLLM, LLMConfig, LLMResponse, Message, Role
from src.core.llm.router import (
    get_current_provider,
    get_llm,
    get_llm_cached,
    list_providers,
    list_tiers,
)

__all__ = [
    "BaseLLM",
    "LLMConfig",
    "LLMResponse",
    "Message",
    "Role",
    "get_current_provider",
    "get_llm",
    "get_llm_cached",
    "list_providers",
    "list_tiers",
]
