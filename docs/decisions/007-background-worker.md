# Decision 007: Background Worker for Content Ingestion

**Date:** 2026-01-30
**Status:** Proposed
**Author:** Claude (AI Assistant)

## Problem

The Security Digest system has:
- FetcherManager that can fetch content from due sources
- Database models and storage layer ready
- Content extraction working

Now we need a production-friendly background process that:
1. Runs continuously to ingest content at regular intervals
2. Handles errors gracefully without crashing
3. Supports graceful shutdown (no stack traces on normal stop)
4. Avoids thundering herd problems (multiple workers hitting sources at exactly the same time)
5. Is configurable for different environments (dev, staging, prod)
6. Can be monitored and managed easily

## Solution

### Architecture

Create a dedicated worker module at `src/workers/security_digest_worker.py` that:
- Runs an infinite loop calling `FetcherManager.fetch_due_sources()`
- Sleeps between iterations with configurable interval + jitter
- Handles SIGINT/SIGTERM for graceful shutdown
- Catches and logs fetch errors without terminating the process
- Loads configuration via the existing config system
- Provides both module and console script entrypoints

```
src/workers/
├── __init__.py
└── security_digest_worker.py   # Background worker implementation

tests/workers/
├── __init__.py
└── test_security_digest_worker.py
```

### Component Details

#### 1. Worker Loop

```python
async def run_worker(config: WorkerConfig) -> None:
    """Main worker loop."""
    while not shutdown_event.is_set():
        try:
            # Fetch due sources
            stats = await manager.fetch_due_sources(
                max_sources=config.max_sources
            )
            logger.info(f"Fetch complete: {stats}")
        except Exception as e:
            # Log but don't crash
            logger.error(f"Fetch error: {e}")

        # Sleep with jitter
        sleep_time = config.interval_seconds + random.uniform(0, config.jitter_seconds)
        await asyncio.sleep(sleep_time)
```

**Key Features:**
- Infinite loop with configurable sleep interval
- Exception handling prevents single fetch errors from crashing the worker
- Shutdown event for graceful termination
- Jitter prevents thundering herd (multiple workers hitting sources simultaneously)

#### 2. Graceful Shutdown

```python
shutdown_event = asyncio.Event()

def handle_signal(signum, frame):
    """Handle SIGINT/SIGTERM for graceful shutdown."""
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    shutdown_event.set()

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)
```

**Why this matters:**
- Prevents incomplete database transactions
- Allows current fetch to complete before stopping
- No ugly stack traces in logs on normal shutdown (Ctrl+C or Docker stop)
- Clean process termination for Docker/systemd

#### 3. Configuration

Configuration via environment variables or config file:

```yaml
# config/workers.yaml
security_digest_worker:
  interval_seconds: 300        # Base sleep interval (5 minutes)
  jitter_seconds: 60          # Random jitter (0-60 seconds)
  max_sources: 10             # Max sources per run
  log_level: INFO             # Logging level
```

**Supported via environment variables:**
- `WORKER_INTERVAL_SECONDS` (default: 300)
- `WORKER_JITTER_SECONDS` (default: 60)
- `WORKER_MAX_SOURCES` (default: 10)
- `WORKER_LOG_LEVEL` (default: INFO)

**Jitter explained:**
- Without jitter: 3 workers all fetch at exactly 10:00:00, 10:05:00, etc.
- With 60s jitter: Worker 1 at 10:00:23, Worker 2 at 10:00:47, Worker 3 at 10:00:11
- Spreads load across time, prevents database contention

#### 4. CLI Entrypoints

**Module invocation:**
```bash
python -m src.workers.security_digest_worker
```

**Console script (via pyproject.toml):**
```bash
pa-worker
```

Configuration in `pyproject.toml`:
```toml
[project.scripts]
pa-worker = "src.workers.security_digest_worker:main"
```

#### 5. Error Handling Strategy

The worker distinguishes between:

1. **Recoverable errors** (log and continue):
   - Individual source fetch failures
   - Network timeouts
   - Temporary database issues
   - NotImplementedError from Twitter/Reddit stubs

2. **Fatal errors** (log and exit):
   - Database connection completely unavailable at startup
   - Invalid configuration
   - Missing required dependencies

**Implementation:**
```python
# Recoverable: catch in loop
try:
    stats = await manager.fetch_due_sources()
except Exception as e:
    logger.error(f"Fetch error: {e}", exc_info=True)
    # Continue to next iteration

# Fatal: let exception propagate to main()
try:
    db = await get_db()
    await db.connect()
except Exception as e:
    logger.critical(f"Cannot connect to database: {e}")
    sys.exit(1)
```

### Production Deployment Patterns

#### Docker (Recommended)

Add to `docker-compose.yaml`:
```yaml
services:
  worker:
    build: .
    command: pa-worker
    environment:
      - WORKER_INTERVAL_SECONDS=300
      - WORKER_MAX_SOURCES=10
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
```

#### Systemd

Create `/etc/systemd/system/pa-worker.service`:
```ini
[Unit]
Description=Personal Assistant Security Digest Worker
After=network.target postgresql.service

[Service]
Type=simple
User=assistant
WorkingDirectory=/opt/personal-assistant
ExecStart=/opt/personal-assistant/venv/bin/pa-worker
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pa-worker
spec:
  replicas: 2  # Multiple workers OK with jitter
  template:
    spec:
      containers:
      - name: worker
        image: personal-assistant:latest
        command: ["pa-worker"]
        env:
        - name: WORKER_INTERVAL_SECONDS
          value: "300"
```

### Monitoring and Observability

The worker emits structured logs suitable for monitoring:

```python
logger.info(
    "Fetch complete",
    extra={
        "sources_checked": stats.sources_checked,
        "sources_fetched": stats.sources_fetched,
        "articles_new": stats.articles_new,
        "duration_seconds": duration,
    }
)
```

**Recommended metrics:**
- `worker.fetch.duration` — How long each fetch cycle takes
- `worker.fetch.sources` — Number of sources processed
- `worker.fetch.articles` — Number of articles saved
- `worker.fetch.errors` — Number of errors encountered
- `worker.uptime` — How long worker has been running

**Health check endpoint (future):**
```python
# Can add a simple HTTP endpoint for k8s liveness probe
@app.get("/health")
async def health():
    return {"status": "ok", "last_fetch": last_fetch_time}
```

## How to Test

### Prerequisites
```bash
# Start infrastructure
docker-compose up -d postgres redis

# Install dependencies
pip install -e .
```

### Run Unit Tests
```bash
pytest tests/workers/test_security_digest_worker.py -v
```

### Test Worker Locally
```bash
# Run with default config
python -m src.workers.security_digest_worker

# Run with custom config
WORKER_INTERVAL_SECONDS=60 WORKER_MAX_SOURCES=5 python -m src.workers.security_digest_worker

# Or use console script
pa-worker
```

### Test Graceful Shutdown
```bash
# Start worker
python -m src.workers.security_digest_worker &
WORKER_PID=$!

# Wait a bit
sleep 5

# Send SIGTERM (should see "shutting down gracefully" message)
kill -TERM $WORKER_PID

# Check it exited cleanly (exit code 0)
wait $WORKER_PID
echo $?
```

### Test in Docker
```bash
# Build and run
docker-compose up worker

# Check logs
docker-compose logs -f worker

# Stop (should see graceful shutdown)
docker-compose stop worker
```

### Verify Fetch Operations
```bash
# Check that sources are being fetched
docker-compose exec postgres psql -U assistant -d assistant \
  -c "SELECT name, last_fetched_at FROM sources ORDER BY last_fetched_at DESC;"

# Check articles are being created
docker-compose exec postgres psql -U assistant -d assistant \
  -c "SELECT COUNT(*) FROM articles WHERE fetched_at > NOW() - INTERVAL '1 hour';"
```

## Alternatives Considered

1. **Cron job** — Simple but:
   - No graceful shutdown
   - No jitter
   - Harder to monitor
   - Doesn't scale horizontally

2. **Celery** — Full-featured but:
   - Heavy dependency
   - Overkill for a single task
   - Requires separate Celery worker process
   - More complex configuration

3. **APScheduler** — In-process scheduler but:
   - Not as robust for long-running processes
   - Harder to manage lifecycle
   - Less suitable for containerized environments

4. **Airflow/Prefect** — Workflow orchestration but:
   - Massive overkill for this use case
   - Adds operational complexity
   - Separate infrastructure to manage

## Decision

Implement a custom background worker using Python's standard library (asyncio, signal, logging). This provides:
- Full control over lifecycle and error handling
- Production-ready features (graceful shutdown, jitter, configurable)
- No heavy dependencies
- Simple to deploy in Docker/systemd/k8s
- Easy to test and debug
- Follows the project's atomicity principle (one worker = one responsibility)
