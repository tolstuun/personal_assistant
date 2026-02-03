# Decision 011: LLM Summarizer Service

**Date:** 2026-02-03
**Status:** Proposed
**Author:** Claude (AI Assistant)

## Problem

Fetched articles need AI-generated summaries before appearing in digests. Currently, articles are stored with their raw content but no summary. We need a reliable summarization service that:

1. Generates concise 2-3 sentence summaries
2. Works with multiple LLM providers (configured via DB settings)
3. Handles failures gracefully without breaking the pipeline
4. Is testable without calling real LLMs

## Solution

### SummarizerService

Create a dedicated service for article summarization at `src/core/services/summarizer.py`:

```python
@dataclass
class SummaryResult:
    summary: str  # 2-3 sentence summary (or title on failure)
    url: str      # Original article URL
    title: str    # Original article title

class SummarizerService:
    async def summarize(title: str, content: str, url: str) -> SummaryResult
```

### Key Design Decisions

**1. No Truncation in v1**
- Pass full content to LLM
- If content is too long, let the LLM error out
- Fallback to title as summary

**2. Reliability Over Quality**
- Any exception → return title as summary
- Never crash the pipeline
- Log all errors for debugging

**3. Configurable via DB Settings**
- `summarizer_provider`: which LLM provider (default: "ollama")
- `summarizer_tier`: which model tier (default: "fast")
- Changes in admin UI apply immediately

**4. Cheap and Stable LLM Config**
- temperature=0.2 (deterministic output)
- max_tokens=200 (enough for 2-3 sentences)

### Implementation

```python
async def summarize(self, title: str, content: str, url: str) -> SummaryResult:
    try:
        provider = await self.settings.get("summarizer_provider")
        tier = await self.settings.get("summarizer_tier")

        llm = get_llm(provider=provider, tier=tier, temperature=0.2, max_tokens=200)

        result = await llm.complete_json(prompt, schema=SUMMARY_SCHEMA)

        summary = result.get("summary", "")
        if not isinstance(summary, str) or not summary.strip():
            return SummaryResult(summary=title, url=url, title=title)

        return SummaryResult(summary=summary.strip(), url=url, title=title)

    except Exception as e:
        logger.warning(f"Summarization failed for '{title}': {e}")
        return SummaryResult(summary=title, url=url, title=title)
```

### Admin Settings

Added to `SettingsService.DEFAULTS`:
- `summarizer_provider`: "ollama" (validates: anthropic/openai/google/ollama)
- `summarizer_tier`: "fast" (validates: fast/smart/smartest)

### CLI Test Mode

Run with:
```bash
python -m src.core.services.summarizer --test <article_id>
```

This loads an article from the database and runs summarization, printing JSON output.

## How to Test

### Prerequisites
```bash
docker-compose up -d postgres
```

### Run Tests
```bash
# Unit tests (mocked LLM)
pytest tests/core/services/test_summarizer.py -v

# Settings validation tests
pytest tests/core/services/test_settings.py -v
```

### Manual Testing

```bash
# Test with a real article (requires LLM config)
python -m src.core.services.summarizer --test <article-uuid>

# Example output:
{
  "title": "New Security Vulnerability in...",
  "url": "https://example.com/article",
  "summary": "Researchers discovered a critical vulnerability..."
}
```

### Verify Settings in Admin UI

1. Visit `/admin/settings`
2. Find `summarizer_provider` and `summarizer_tier`
3. Try setting invalid values → should see validation error

## Alternatives Considered

### 1. Truncate Long Content
- **Pro:** Always works within token limits
- **Con:** May lose important context
- **Decision:** Defer to v2; prefer reliability over partial content

### 2. Retry on Failure
- **Pro:** Better success rate
- **Con:** Slower, more expensive, more complex
- **Decision:** Keep simple for v1; title fallback is acceptable

### 3. Hardcode Provider/Tier
- **Pro:** Simpler, no DB dependency
- **Con:** Can't change without code deploy
- **Decision:** Use DB settings for flexibility
