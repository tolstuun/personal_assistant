# Changelog

## 2026-01-29

### Content Fetcher for Security Digest (New)
Added content fetching primitives for the Security Digest system:

- **Website Fetcher** (`src/core/primitives/fetchers/website.py`) — Fetches articles from websites. Downloads listing pages, extracts article links, then fetches each article and extracts content using trafilatura.

- **Fetcher Manager** (`src/core/primitives/fetchers/manager.py`) — Orchestrates fetching from all sources. Checks which sources are due (based on fetch interval), dispatches to correct fetcher, handles deduplication by URL, applies keyword filtering, and stores articles.

- **Twitter/Reddit Stubs** — Placeholder implementations for future Twitter and Reddit support.

**Features:**
- Automatic article link detection (skips navigation, footers, tag pages)
- Content extraction using trafilatura (handles most news sites automatically)
- Keyword filtering using source and category keywords
- URL deduplication (won't fetch same article twice)
- Configurable fetch intervals per source

**Testing:**
```bash
# Test fetching from a URL directly (dry run)
python -m src.core.primitives.fetchers.test_fetch --url https://krebsonsecurity.com/

# Test fetching from a database source
python -m src.core.primitives.fetchers.test_fetch <source-uuid>
```

**New dependency:** trafilatura (for article content extraction)

## 2026-01-28

### LLM Config Redesign (New)
Redesigned LLM configuration to make switching between providers easy:

- **Single setting to switch providers:** Change `current_provider` to use a different LLM backend (anthropic, openai, google, ollama)
- **Model tiers:** Use `fast`, `smart`, or `smartest` instead of remembering specific model names. Each provider maps these to their best models.
- **Task overrides:** Optionally assign tasks like `summarization` or `code_review` to specific tiers
- **Per-provider API keys:** Each provider has its own API key in the config

**Usage examples:**
```python
from src.core.llm import get_llm

llm = get_llm()                      # Default model from current provider
llm = get_llm(tier="fast")           # Fast model (e.g., claude-haiku)
llm = get_llm(task="summarization")  # Uses task_overrides if defined
llm = get_llm(provider="ollama")     # Temporarily use different provider
```

**How to switch providers:** Edit `config/llm.yaml` and change `current_provider: anthropic` to `current_provider: openai` (or google, ollama).

### CI/CD Workflow (New)
Added GitHub Actions workflow for automated testing and deployment:

- **On every PR:** Runs linting (`ruff check`) and tests (`pytest`)
- **On merge to master:** Deploys to Hetzner server via SSH

The workflow ensures all code is tested before it can be merged, and automatically deploys when changes reach master.

**How to verify:** Check the Actions tab in GitHub after creating a PR or merging to master.

### Storage Layer (New)
Added complete storage layer with four backends:

- **PostgreSQL** (`src/core/storage/postgres.py`) — For storing user data, agent states, and conversation history. Uses SQLAlchemy with async support and connection pooling.

- **Redis Cache** (`src/core/storage/redis_cache.py`) — For caching frequently accessed data and session management. Supports JSON serialization and TTL.

- **Vector Store** (`src/core/storage/vector_store.py`) — For semantic search and RAG. Uses Qdrant to store document embeddings and find similar content.

- **File Storage** (`src/core/storage/file_storage.py`) — For storing documents, images, and reports. Uses MinIO (S3-compatible) with presigned URL support.

All components follow the same pattern:
1. Abstract base class defining the interface
2. Concrete implementation
3. Factory function for easy access (`get_db()`, `get_cache()`, etc.)

**How to test:** Run `docker-compose up -d` to start services, then `pytest tests/core/storage/` to run storage tests.

### Earlier Changes

- Project documentation structure established
- Added CLAUDE.md with workflow rules and project standards
- Created docs/decisions/ for architecture decision records
- Created docs/guides/ for owner how-to guides
