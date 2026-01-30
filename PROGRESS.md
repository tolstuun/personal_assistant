# Progress

Tracking Personal Assistant development progress.

## Current Status

**Phase 2: First Agent (Security Digest)** — In Progress

## Changelog

### 2026-01-30: Background Worker

**Done:**
- [x] Created decision doc: docs/decisions/007-background-worker.md
- [x] src/workers/security_digest_worker.py — production-ready worker
- [x] tests/workers/test_security_digest_worker.py — comprehensive tests
- [x] Added pa-worker console script to pyproject.toml
- [x] Updated README with worker instructions
- [x] Updated docs/changelog.md

**Features:**
- Infinite loop with configurable interval and jitter
- Graceful shutdown on SIGINT/SIGTERM
- Error handling prevents crashes
- Configurable via environment variables or YAML
- Suitable for Docker, systemd, or Kubernetes deployment

### 2026-01-29: Content Fetcher

**Done:**
- [x] Created decision doc: docs/decisions/006-content-fetcher.md
- [x] src/core/primitives/fetchers/website.py — Website fetcher using trafilatura
- [x] src/core/primitives/fetchers/manager.py — Fetcher orchestration
- [x] src/core/primitives/fetchers/twitter.py — Twitter stub
- [x] src/core/primitives/fetchers/reddit.py — Reddit stub
- [x] src/core/primitives/fetchers/test_fetch.py — CLI test script
- [x] tests/core/primitives/fetchers/ — 35 tests
- [x] Added trafilatura dependency

**Features:**
- Automatic article link extraction from listing pages
- Content extraction using trafilatura (readability algorithm)
- Keyword filtering (source + category keywords)
- URL deduplication
- Configurable fetch intervals

### 2026-01-28: LLM Config Redesign

**Done:**
- [x] Created decision doc: docs/decisions/003-llm-config-redesign.md
- [x] config/llm.example.yaml — new provider-based config structure
- [x] src/core/llm/router.py — rewritten with tier/task/provider support
- [x] src/core/llm/__init__.py — updated exports
- [x] tests/core/llm/test_router.py — comprehensive tests

**Features:**
- Switch providers with a single config change (`current_provider`)
- Model tiers: fast/smart/smartest abstract away model names
- Task overrides: optional mapping of tasks to tiers
- Backwards compatible with old config format

### 2026-01-28: CI/CD Workflow

**Done:**
- [x] Created decision doc: docs/decisions/002-ci-cd-workflow.md
- [x] .github/workflows/ci-cd.yml — GitHub Actions workflow
- [x] Automated linting and testing on PRs
- [x] Automated deployment to Hetzner on master merge

### 2026-01-28: Storage Layer Implementation

**Done:**
- [x] Created decision doc: docs/decisions/001-storage-layer-design.md
- [x] config/storage.example.yaml — storage configuration
- [x] src/core/storage/base.py — abstract base classes
- [x] src/core/storage/exceptions.py — storage exceptions
- [x] src/core/storage/postgres.py — PostgreSQL with SQLAlchemy async
- [x] src/core/storage/redis_cache.py — Redis caching with JSON support
- [x] src/core/storage/vector_store.py — Qdrant vector search
- [x] src/core/storage/file_storage.py — MinIO/S3 file storage
- [x] tests/core/storage/ — tests for all components

**Decisions made:**
- All storage components follow the same pattern: abstract base class + concrete implementation + factory function
- Singleton pattern for global instances (get_db, get_cache, etc.)
- Async-first design throughout
- Qdrant for vector search (self-hosted, S3-compatible)

### 2025-01-09: Project Initialization

**Done:**
- [x] Created project structure
- [x] README.md
- [x] ARCHITECTURE.md — architecture description
- [x] docker-compose.yaml — infrastructure
- [x] pyproject.toml — Python dependencies
- [x] src/core/llm/ — basic LLM abstraction
- [x] src/core/config/ — config loading
- [x] src/core/primitives/fetcher.py — first primitive
- [x] Example configs

**Decisions made:**
- Not using LangChain (excessive abstraction)
- Using LiteLLM for LLM provider unification
- Configs in YAML, separated from code
- Atomic primitives instead of monolithic agents

## Plan

### Phase 1: Foundation ✅
- [x] Project structure
- [x] Docker Compose (PostgreSQL, Redis, Qdrant, MinIO)
- [x] LLM abstraction
- [x] Config loader
- [x] First primitive (Fetcher)

### Phase 2: First Agent (Security Digest) 🔄
- [x] Data model (categories, sources, articles, digests)
- [x] Admin UI for managing sources
- [x] Content fetcher primitive (website fetcher)
- [x] Background worker for content ingestion
- [ ] LLM summarization and scoring
- [ ] Digest generation (HTML output)
- [ ] Manual CLI execution

### Phase 3: Orchestrator + API
- [ ] FastAPI server
- [ ] Task queue (Redis)
- [ ] Scheduler (cron)
- [ ] Basic authentication

### Phase 4: Storage Layer ✅
- [x] PostgreSQL abstractions (SQLAlchemy async)
- [x] Redis cache layer
- [x] Vector DB (Qdrant) for RAG
- [x] File storage (MinIO/S3)

### Phase 5+: Remaining Agents
- [ ] Job Hunter
- [ ] Calendar Sync
- [ ] Code Assistant
- [ ] Market Intel
- [ ] Red Team Tools

## Notes

### Architecture Discussion (2025-01-09)

Key requirements:
1. Modularity — each agent is independent
2. Atomicity — primitives do one thing
3. LLM swappability — via config, not code
4. Fighting hallucinations — verification at every step
5. Multilingual — Chinese, Japanese, etc.
6. Personal story for Job Hunter — separate profile in configs

For Job Hunter, need a multi-layered profile:
- `story.yaml` — narrative, how I position myself
- `facts.yaml` — concrete achievements with metrics
- LLM adapts CV using BOTH sources
