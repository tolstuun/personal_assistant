# Changelog

## 2026-02-12

### Workers Config Loading Fix (Fix)
The background worker reads its settings (interval, jitter, max sources, log level) from the config under `workers.security_digest_worker`, but the config loader wasn't loading `workers.yaml` at all. The worker silently fell back to hardcoded defaults.

- **Config loader updated** — Now loads `config/workers.example.yaml` (defaults) and `config/workers.yaml` (overrides), same as other config files.
- **Example file added** — `config/workers.example.yaml` with sensible defaults (interval: 300s, jitter: 60s, max sources: 10, log level: INFO).
- **Gitignore updated** — `config/workers.yaml` is gitignored so deployment-specific overrides stay on the server.

**How to test:**
```bash
pytest tests/core/config/test_loader.py -v
```

For technical details, see: `docs/decisions/016-workers-config-loading.md`

### Job Run Logging (New)
Added a `job_runs` database table and service to record background job executions (fetch worker, future digest scheduler, etc.):

- **JobRun model** — Stores job name, status (running/success/error/skipped), start and finish times, small stats as JSON, and error messages.
- **JobRunService** — Three methods: `start()` to begin tracking a run, `finish()` to record the outcome, `get_latest()` to check the most recent run.
- **Alembic migration 004** — Creates the `job_runs` table with indexes on `job_name` and `started_at`.

This is the data foundation only — no admin UI or worker changes yet. Those come in follow-up PRs.

**How to test:**
```bash
docker-compose up -d postgres
pytest tests/core/services/test_job_runs.py -v
```

For technical details, see: `docs/decisions/017-job-run-logging.md`

## 2026-02-07

### Browser Fetcher Timeout Fix (Fix)
Fixed timeout issues with the Playwright browser fetcher that caused some sites (e.g. msspalert.com) to hang:

- **Faster wait strategy** — Changed from `networkidle` (waits for all network activity to stop) to `domcontentloaded` (waits for HTML to parse). Most content is available at this point.
- **Longer timeout** — Increased from 30s to 60s for slow sites.
- **Automatic fallback** — If `domcontentloaded` times out, retries with `commit` (page started receiving data). This gets at least partial content from very slow sites.

**No action needed** — the fix is automatic.

## 2026-02-06

### Version-Controlled Deploy Script (Improvement)
Moved the deploy script into the repository (`deploy/deploy.sh`) so it's version-controlled and handles all runtime dependencies automatically:

- **Git pull** — fetches latest code
- **Python dependencies** — installs packages via `pip3 install -e .`
- **Playwright browser** — installs Chromium for the browser fetcher
- **Database migrations** — runs `alembic upgrade head`
- **Service restart** — restarts systemd workers

**No manual steps needed after merge to master** — CI runs the deploy script automatically.

For technical details, see: `docs/decisions/015-deploy-script.md`

### Browser Fetcher for Blocked Websites (New)
Added Playwright-based browser fallback for websites that block simple HTTP requests:

- **Browser Fetcher** (`src/core/primitives/fetchers/browser.py`) — Uses a headless Chromium browser via Playwright to fetch pages that return 403 or 429 to regular HTTP requests. Mimics a real user with realistic user-agent and viewport.

- **Automatic Fallback** — WebsiteFetcher now automatically retries with the browser when HTTP gets blocked. A domain cache remembers which sites need the browser, so subsequent fetches skip the HTTP attempt.

- **Admin Setting** — `browser_fetcher_enabled` (default: enabled). Disable via admin Settings page if you don't want browser fallback.

**New dependency:** playwright (requires `playwright install chromium` on the server)

**How to test:**
```bash
pytest tests/core/primitives/fetchers/test_browser.py tests/core/primitives/fetchers/test_website.py -v
```

For technical details, see: `docs/decisions/014-browser-fetcher.md`

## 2026-02-05

### Telegram Notification on Digest (New)
When a digest is generated, the bot now sends a Telegram notification to all configured users:

- **TelegramNotifier** (`src/core/services/notifier.py`) — Lightweight service for sending Telegram messages. Reads bot token and chat IDs from `config/telegram.yaml`. Never crashes — logs errors and continues.

- **Automatic notification** — After a digest is created, a message is sent with the digest date, article count, and a link to view it. The `notified_at` timestamp is recorded on the Digest record.

- **Configurable** — Controlled by the `telegram_notifications` setting (default: enabled). Disable via admin Settings page.

**How it works:** Generate a digest (via dashboard button or CLI) and you'll get a Telegram message with a link to the digest.

For technical details, see: `docs/decisions/013-digest-telegram-notification.md`

### Digest Generator (New)
Added a service that generates daily digests from fetched articles:

- **DigestService** (`src/core/services/digest.py`) — Collects unprocessed articles (those not yet in a digest), summarizes any that lack summaries using the configured LLM, groups them by section, and generates a standalone HTML page.

- **HTML Output** — Clean, mobile-friendly HTML digest saved to `data/digests/`. Each digest has sections (Security News, Product News, Market) with article titles linked to original URLs and AI-generated summaries.

- **Admin UI** — "Generate Digest Now" button on the dashboard for manual testing. Shows success/failure result and links to the generated digest.

- **CLI** — `python -m src.core.services.digest --generate` for command-line generation.

**How to use:**
1. Make sure articles have been fetched (the background worker does this automatically)
2. Click "Generate Digest Now" on the dashboard, or run the CLI command
3. View the generated HTML at `/digests/digest-YYYY-MM-DD.html`

**How to test:**
```bash
pytest tests/core/services/test_digest.py -v
```

For technical details, see: `docs/decisions/012-digest-generator.md`

### Settings Dropdowns for Summarizer (Improvement)
Changed `summarizer_provider` and `summarizer_tier` from free-text inputs to dropdown menus in the admin settings page:

- **Summarizer Provider** — Now a dropdown with options: ollama, anthropic, openai, google
- **Summarizer Tier** — Now a dropdown with options: fast, smart, smartest

This prevents typos and makes it clear which values are valid. Also added a reusable `select` field type to the settings system, so future settings with fixed options can use dropdowns too.

**No action needed** — existing values are unchanged. The dropdowns just make editing easier.

## 2026-02-03

### LLM Summarizer Service (New)
Added a service for generating AI summaries of fetched articles:

- **SummarizerService** (`src/core/services/summarizer.py`) — Generates 2-3 sentence summaries using the configured LLM provider. Falls back to article title if summarization fails (for any reason).

- **Database Settings** — Provider and model tier are configurable via admin UI:
  - `summarizer_provider` — Which LLM to use (anthropic, openai, google, ollama). Default: ollama
  - `summarizer_tier` — Which model tier (fast, smart, smartest). Default: fast

- **Reliability First** — The service never crashes. If the LLM call fails, times out, or returns invalid JSON, it returns the article title as the summary and logs the error.

**How to test:**
```bash
# Unit tests
pytest tests/core/services/test_summarizer.py -v

# Manual test with a real article
python -m src.core.services.summarizer --test <article-uuid>
```

**How to configure:** Visit `/admin/settings` and edit `summarizer_provider` or `summarizer_tier`.

For technical details, see: `docs/decisions/011-llm-summarizer.md`

## 2026-02-02

### Admin Settings Page (New)
Added a Settings page to the admin UI for managing system configuration:

- **Settings Page** (`/admin/settings`) — View and edit system settings through the web UI. No more editing config files for common settings.

- **Database-Stored Settings** — Settings are stored in a new `settings` table. Changes take effect without restarting services.

- **Configurable Settings:**
  - **Fetch Interval** — How often to fetch new content (default: 60 minutes)
  - **Fetch Worker Count** — Number of parallel workers to run (default: 3)
  - **Digest Time** — When to generate the daily digest (default: 08:00)
  - **Telegram Notifications** — Enable/disable notifications (default: enabled)
  - **Digest Sections** — Which sections to include (default: security_news, product_news, market)

- **Worker Integration** — The background worker now reads `fetch_interval_minutes` from the database. Change the interval in the admin UI and the worker picks it up on the next cycle.

- **Multi-Worker Support** — Run multiple parallel workers for faster content ingestion. Workers use SKIP LOCKED to avoid duplicate work.

**How to use:**
1. Visit `/admin/settings` (requires admin login)
2. Edit any setting and click "Save"
3. Changes are applied immediately (worker reads on next cycle)

**How to reset:** Click "Reset" next to any customized setting to restore the default value.

### Multi-Worker Deployment (New)
Added support for running multiple parallel fetcher workers:

- **Systemd Template Unit** (`deploy/pa-fetcher@.service`) — Supports running N worker instances using systemd templates.

- **Worker Manager Script** (`pa-worker-manager`) — Reads `fetch_worker_count` from database and manages worker instances.

**How to run multiple workers:**
```bash
# Using the manager script (recommended)
pa-worker-manager start   # Starts workers based on fetch_worker_count setting
pa-worker-manager stop    # Stops all workers
pa-worker-manager reload  # Adjusts count to match setting
pa-worker-manager status  # Shows running workers

# Manual control with systemd
sudo systemctl start pa-fetcher@{1..3}   # Start workers 1, 2, 3
sudo systemctl stop pa-fetcher@2         # Stop worker 2
sudo journalctl -u 'pa-fetcher@*' -f     # Follow all worker logs
```

**Why it's safe:** FetcherManager uses `SELECT ... FOR UPDATE SKIP LOCKED` so workers automatically skip sources being processed by other workers.

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
