# Changelog

## 2026-02-02

### Admin Settings Page (New)
Added a Settings page to the admin UI for managing system configuration:

- **Settings Page** (`/admin/settings`) — View and edit system settings through the web UI. No more editing config files for common settings.

- **Database-Stored Settings** — Settings are stored in a new `settings` table. Changes take effect without restarting services.

- **Configurable Settings:**
  - **Fetch Interval** — How often to fetch new content (default: 60 minutes)
  - **Digest Time** — When to generate the daily digest (default: 08:00)
  - **Telegram Notifications** — Enable/disable notifications (default: enabled)
  - **Digest Sections** — Which sections to include (default: security_news, product_news, market)

- **Worker Integration** — The background worker now reads `fetch_interval_minutes` from the database. Change the interval in the admin UI and the worker picks it up on the next cycle.

- **Systemd Service** — Added `deploy/pa-worker.service` for running the worker as a system service.

**How to use:**
1. Visit `/admin/settings` (requires admin login)
2. Edit any setting and click "Save"
3. Changes are applied immediately (worker reads on next cycle)

**How to reset:** Click "Reset" next to any customized setting to restore the default value.

For technical details, see: `docs/decisions/010-admin-settings.md`

### Article Persistence Scalability (Improvement)
Replaced per-article duplicate checking with bulk Postgres UPSERT for better performance and concurrency safety:

- **Bulk INSERT with ON CONFLICT DO NOTHING** — Instead of checking each URL with a separate SELECT query (N+1 pattern), all articles are now inserted in a single statement. Postgres handles duplicates automatically.

- **Concurrency Safe** — Multiple workers can now insert overlapping URLs without causing unique constraint violations. The database handles the race condition atomically.

- **Accurate Stats via RETURNING** — Uses Postgres RETURNING clause to count exactly which URLs were inserted vs. which were duplicates. More reliable than rowcount.

**Performance improvement:**
- Old: 50 articles = 100 queries (50 SELECT + 50 INSERT)
- New: 50 articles = 1 query (bulk INSERT)

**No changes needed:** This is an internal improvement. All filtering logic (date cutoff, keyword matching) remains identical. No API or config changes.

**Testing:** Two new integration tests verify correct behavior:
- `test_bulk_insert_counts_duplicates` — Verifies duplicate URLs in same batch are handled correctly
- `test_concurrent_insert_same_url` — Verifies concurrent workers don't error on overlapping URLs

For technical details, see: `docs/decisions/009-article-upsert.md`

## 2026-01-30

### Background Worker for Content Ingestion (New)
Added a production-ready background worker that automatically fetches content from Security Digest sources:

- **Worker Module** (`src/workers/security_digest_worker.py`) — Runs continuously and fetches content at regular intervals. Handles errors gracefully, supports graceful shutdown, and uses jitter to prevent thundering herd problems.

- **CLI Entrypoints** — Can be run as `python -m src.workers.security_digest_worker` or using the `pa-worker` console script.

- **Configuration** — Supports both environment variables and config files. Key settings:
  - `WORKER_INTERVAL_SECONDS` — How long to wait between fetch cycles (default: 300)
  - `WORKER_JITTER_SECONDS` — Random jitter to add (default: 60)
  - `WORKER_MAX_SOURCES` — Max sources per cycle (default: 10)
  - `WORKER_LOG_LEVEL` — Logging level (default: INFO)

**Features:**
- Graceful shutdown on SIGINT/SIGTERM (no stack traces, completes current fetch)
- Error handling that prevents crashes (logs errors and continues)
- Jitter prevents multiple workers from hitting sources at the same time
- Detailed logging with fetch statistics
- Works in Docker, systemd, or Kubernetes

**How to run:**
```bash
# Run locally
pa-worker

# Run with custom settings
WORKER_INTERVAL_SECONDS=120 pa-worker

# Run in Docker
docker-compose up -d worker
```

**How to stop:**
- Press Ctrl+C when running in foreground
- `docker-compose stop worker` when running in Docker
- Worker completes current fetch and exits cleanly

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
