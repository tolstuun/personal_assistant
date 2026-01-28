# Changelog

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
