"""
LLM module — unified interface to language models.

Usage:
    from src.core.llm import get_llm
    
    llm = get_llm()
    response = await llm.complete("Hello!")
"""

from src.core.llm.base import BaseLLM, LLMConfig, LLMResponse, Message, Role
from src.core.llm.router import get_llm, get_llm_cached

__all__ = [
    "BaseLLM",
    "LLMConfig", 
    "LLMResponse",
    "Message",
    "Role",
    "get_llm",
    "get_llm_cached",
]
