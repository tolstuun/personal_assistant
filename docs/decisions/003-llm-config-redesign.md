# Decision 003: LLM Config Redesign

**Date:** 2026-01-28
**Status:** Proposed
**Author:** Claude (AI Assistant)

## Problem

The current LLM config has several issues:

1. **Hard to switch providers** - Changing from Claude to OpenAI requires editing multiple model names throughout the config
2. **Task models are required** - The config forces you to specify a model for each task type, even when you just want the default
3. **No clear provider separation** - API keys and settings are mixed together
4. **Model names are scattered** - If you want to use a different model, you have to know the exact provider-specific name

## Solution

### New Config Structure

```yaml
# LLM Configuration
# Change current_provider to switch everything at once

current_provider: anthropic  # Options: anthropic, openai, google, ollama

providers:
  anthropic:
    api_key: ${ANTHROPIC_API_KEY}
    default_model: claude-sonnet-4-20250514
    models:
      fast: claude-haiku-3-5-20241022
      smart: claude-sonnet-4-20250514
      smartest: claude-opus-4-20250514

  openai:
    api_key: ${OPENAI_API_KEY}
    default_model: gpt-4o
    models:
      fast: gpt-4o-mini
      smart: gpt-4o
      smartest: gpt-4o

  google:
    api_key: ${GOOGLE_API_KEY}
    default_model: gemini-1.5-pro
    models:
      fast: gemini-1.5-flash
      smart: gemini-1.5-pro
      smartest: gemini-1.5-pro

  ollama:
    base_url: http://localhost:11434
    default_model: llama3
    models:
      fast: llama3
      smart: llama3:70b
      smartest: llama3:70b

# Global settings (apply to all providers)
settings:
  temperature: 0.7
  max_tokens: 4096
  timeout: 60.0

# Optional: Override model tier for specific tasks
# Uses aliases (fast/smart/smartest), not model names
# If not specified, uses the provider's default_model
task_overrides:
  summarization: fast
  code_review: smartest
```

### How It Works

1. **Switch providers instantly** - Just change `current_provider` from `anthropic` to `openai`
2. **Provider-specific API keys** - Each provider has its own `api_key` field
3. **Model tiers** - Use `fast`, `smart`, `smartest` aliases instead of remembering model names
4. **Task overrides are optional** - If not specified, uses the provider's `default_model`

### API Usage

```python
from src.core.llm import get_llm

# Get default model from current provider
llm = get_llm()

# Get a specific tier (resolves to provider's model)
llm = get_llm(tier="fast")      # Gets claude-haiku or gpt-4o-mini depending on provider
llm = get_llm(tier="smartest")  # Gets claude-opus or gpt-4o depending on provider

# Override provider for this call only
llm = get_llm(provider="ollama")

# Get model for a specific task (uses task_overrides if defined)
llm = get_llm(task="summarization")  # Uses "fast" tier

# Still works: specify exact model name
llm = get_llm(model="gpt-4o-mini")
```

## How to Test

```bash
# After making changes, run the tests
pytest tests/core/llm/ -v

# Manual test (requires API key set)
python -c "
from src.core.llm import get_llm
llm = get_llm()
print(f'Using: {llm.get_model_name()}')
"
```

## Migration

The old config format will continue to work (backwards compatible). The new format is opt-in.

## Alternatives Considered

1. **Environment variable for provider switching** - Rejected because config file is easier to manage and version
2. **Separate config files per provider** - Rejected because it's more complex and harder to switch
3. **Keep current structure** - Rejected because switching providers is too cumbersome
