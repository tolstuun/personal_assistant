"""
Base interface for LLM providers.

All LLM providers must implement this interface.
This ensures we can swap providers without changing agent code.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Role(str, Enum):
    """Message roles in conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class Message:
    """A single message in conversation."""
    role: Role
    content: str


@dataclass
class LLMResponse:
    """Response from LLM provider."""
    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    raw_response: Any = None


@dataclass
class LLMConfig:
    """Configuration for LLM provider."""
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: float = 60.0
    extra: dict[str, Any] = field(default_factory=dict)


class BaseLLM(ABC):
    """
    Abstract base class for LLM providers.
    
    Usage:
        llm = SomeLLMProvider(config)
        response = await llm.complete("Your prompt")
        
        # Or with messages
        response = await llm.chat([
            Message(Role.SYSTEM, "You are helpful assistant"),
            Message(Role.USER, "Hello!"),
        ])
    """
    
    def __init__(self, config: LLMConfig):
        self.config = config
    
    @abstractmethod
    async def complete(self, prompt: str) -> LLMResponse:
        """Simple completion with a single prompt."""
        pass
    
    @abstractmethod
    async def chat(self, messages: list[Message]) -> LLMResponse:
        """Chat completion with message history."""
        pass
    
    @abstractmethod
    async def complete_json(self, prompt: str, schema: dict[str, Any] | None = None) -> dict:
        """Completion that returns structured JSON."""
        pass
    
    def get_model_name(self) -> str:
        """Return the model name."""
        return self.config.model
