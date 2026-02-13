# Architecture

This document describes the Personal Assistant architecture. Updated as the project evolves.

## Overview

```
┌────────────────────────────────────────────────────────────────────────────┐
│                              INTERFACES                                    │
│  Telegram Bot  │  Admin UI (/admin)  │  CLI  │  REST API                  │
└───────────────────────────────┬────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                         FASTAPI GATEWAY                                    │
│  - Authentication                                                         │
│  - Request routing                                                        │
│  - Admin UI (HTMX + Tailwind)                                             │
└───────────────────────────────┬────────────────────────────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼                               ▼
┌──────────────────────────┐  ┌─────────────────────────────────────────────┐
│     BACKGROUND WORKERS   │  │                ORCHESTRATOR                  │
│  - Fetch Worker          │  │  - Task queue (Redis)                       │
│  - Digest Scheduler      │  │  - Scheduler (cron jobs)                    │
│  (write job_runs;        │  │  - Human-in-the-loop flags                  │
│   scheduler → Telegram)  │  │                                              │
└────────────┬─────────────┘  └──────┬──────────────────────────────────────┘
             │                       │
             ▼                       ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                              CORE                                          │
│  LLM Layer  │  Primitives  │  Services  │  Storage  │  Config             │
└────────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                         INFRASTRUCTURE                                     │
│  PostgreSQL (+ job_runs)  │  Redis  │  Qdrant  │  MinIO                   │
└────────────────────────────────────────────────────────────────────────────┘
```

### Operational Transparency
Background workers (Fetch Worker, Digest Scheduler) record each execution cycle to the `job_runs` table in PostgreSQL via `JobRunService`. The Digest Scheduler generates digests daily at `digest_time` (UTC) and optionally sends Telegram notifications. The Admin UI at `/admin/operations` surfaces job runs, digest status, and scheduling info so the owner can see at a glance whether jobs are running, succeeding, or failing — without checking server logs.

## Principles

### 1. Atomicity
Each component does **one thing**. Instead of a monolithic "find Gartner reports" — a chain of primitives:
```
Discoverer → Fetcher → Parser → Extractor → Verifier → Storage → Notifier
```

### 2. LLM Interchangeability
All LLM calls go through the `src/core/llm/` abstraction. Switching providers means changing config, not code.

### 3. Configuration Separated from Code
- `config/llm.yaml` — providers, models, keys
- `config/sources/` — data sources for crawling
- `config/agents/` — settings for each agent
- `config/my_profile/` — personal data for Job Hunter

### 4. Verification Against Hallucinations
- Structured output (JSON, not free text)
- Checking extracted facts against source text
- Double verification for critical data
- Explicit "NOT_FOUND" instead of making things up

### 5. Multilingual Support
Support for any language through Cloud LLM (Claude, GPT-4). Chinese, Japanese, etc. are processed at extraction level, translated to working language (RU/EN).

## Components

### Core / LLM (`src/core/llm/`)

**Status:** ✅ Basic version ready

**Purpose:** Unified interface to LLM providers

**Files:**
- `base.py` — abstract interface `BaseLLM`
- `router.py` — provider selection by task/model
- `providers/litellm_provider.py` — implementation via LiteLLM

**Usage:**
```python
from src.core.llm import get_llm

llm = get_llm()  # Gets default from config
response = await llm.complete("Your prompt")

# Or specific model
llm = get_llm(model="claude-sonnet-4-20250514")
```

### Core / Primitives (`src/core/primitives/`)

**Status:** ✅ Fetcher ready

**Purpose:** Atomic operations that agents are built from

**Primitives:**
- `fetcher.py` — download content from URL
- `parser.py` — HTML/PDF → text (TODO)
- `extractor.py` — extract structured data via LLM (TODO)
- `verifier.py` — verify facts against source (TODO)
- `translator.py` — translation (TODO)
- `deduplicator.py` — deduplication (TODO)

### Core / Storage (`src/core/storage/`)

**Status:** 🔲 Planned

**Purpose:** Abstraction over data stores

**Planned components:**
- `postgres.py` — main database
- `redis_cache.py` — cache, queues
- `vector_store.py` — vector DB for RAG
- `file_storage.py` — S3/MinIO for files

### Core / Config (`src/core/config/`)

**Status:** ✅ Basic version ready

**Purpose:** Loading and validating YAML configs

### Agents (`src/agents/`)

**Status:** 🔲 Planned

Each agent is an independent module with its own logic.

Planned agents:
1. **Security Digest** — cybersecurity news collection
2. **Job Hunter** — CV adaptation, job applications
3. **Calendar Sync** — calendar synchronization
4. **Code Assistant** — coding help, documentation RAG
5. **Market Intel** — analytical reports, Gartner, etc.
6. **Red Team Tools** — training tools

### Orchestrator (`src/orchestrator/`)

**Status:** 🔲 Planned

**Purpose:** Agent coordination, task queues, scheduler

### API (`src/api/`)

**Status:** 🔲 Planned

**Purpose:** FastAPI server, REST API for all interfaces

## Decisions and Rationale

### Why not LangChain?

**Reasons:**
1. Excessive abstraction — adds complexity without benefit
2. Magic instead of control — hard to debug
3. Conflicts with atomicity — pulls toward their structure
4. Many dependencies
5. Frequent breaking changes

**Alternative:** LiteLLM for LLM unification + custom primitives

### Why LiteLLM?

- Simple unified API to 100+ providers
- Minimal dependencies
- Easy provider switching without code changes
- Actively maintained

### Why YAML for configs?

- Human-readable
- Easy to version in git
- Easy to edit without UI
- Flexible enough for our needs

## Dependencies

### Python packages (main)
- `litellm` — LLM API unification
- `fastapi` + `uvicorn` — API server
- `httpx` — HTTP client
- `pydantic` — data validation
- `pyyaml` — config handling
- `asyncpg` — PostgreSQL
- `redis` — cache and queues
- `qdrant-client` — vector DB

### Infrastructure (Docker)
- PostgreSQL 16
- Redis 7
- Qdrant (vector DB)
- MinIO (S3-compatible storage)

## Further Development

See [PROGRESS.md](PROGRESS.md) for current status and plans.
