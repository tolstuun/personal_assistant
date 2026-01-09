"""
LiteLLM provider implementation.

LiteLLM provides unified API to 100+ LLM providers:
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- Google (Gemini)
- Local models via Ollama
- And many more

See: https://docs.litellm.ai/docs/providers
"""

import json
import logging
from typing import Any

import litellm

from src.core.llm.base import BaseLLM, LLMConfig, LLMResponse, Message

logger = logging.getLogger(__name__)


class LiteLLMProvider(BaseLLM):
    """
    LLM provider using LiteLLM library.
    
    Supports all providers that LiteLLM supports. Model format:
    - "gpt-4" or "openai/gpt-4" — OpenAI
    - "claude-sonnet-4-20250514" or "anthropic/claude-sonnet-4-20250514" — Anthropic
    - "gemini/gemini-pro" — Google
    - "ollama/llama3" — Local Ollama
    
    API keys are read from environment variables:
    - OPENAI_API_KEY
    - ANTHROPIC_API_KEY
    - etc.
    
    Or can be passed in config.extra["api_key"]
    """
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        litellm.drop_params = True
        self._api_key = config.extra.get("api_key")
    
    async def complete(self, prompt: str) -> LLMResponse:
        """Simple completion with a single prompt."""
        messages = [{"role": "user", "content": prompt}]
        return await self._call(messages)
    
    async def chat(self, messages: list[Message]) -> LLMResponse:
        """Chat completion with message history."""
        formatted = [{"role": m.role.value, "content": m.content} for m in messages]
        return await self._call(formatted)
    
    async def complete_json(self, prompt: str, schema: dict[str, Any] | None = None) -> dict:
        """Completion that returns structured JSON."""
        json_prompt = f"{prompt}\n\nRespond with valid JSON only. No markdown, no explanation."
        
        if schema:
            json_prompt += f"\n\nExpected schema:\n```json\n{json.dumps(schema, indent=2)}\n```"
        
        response = await self.complete(json_prompt)
        content = response.content.strip()
        
        # Remove markdown code blocks if present
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1])
        
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {content[:500]}")
            raise ValueError(f"LLM response is not valid JSON: {e}") from e
    
    async def _call(self, messages: list[dict]) -> LLMResponse:
        """Internal method to call LiteLLM."""
        try:
            kwargs: dict[str, Any] = {
                "model": self.config.model,
                "messages": messages,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
                "timeout": self.config.timeout,
            }
            
            if self._api_key:
                kwargs["api_key"] = self._api_key
            
            for key, value in self.config.extra.items():
                if key != "api_key":
                    kwargs[key] = value
            
            response = await litellm.acompletion(**kwargs)
            
            return LLMResponse(
                content=response.choices[0].message.content,
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                raw_response=response,
            )
            
        except Exception as e:
            logger.error(f"LiteLLM call failed: {e}")
            raise
