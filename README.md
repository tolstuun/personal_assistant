# Personal Assistant

A modular AI assistant with atomic components.

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/avoitenko16/personal_assistant.git
cd personal_assistant

# 2. Copy config
cp config/llm.example.yaml config/llm.yaml
# Add your API keys to config/llm.yaml

# 3. Start infrastructure
docker-compose up -d

# 4. Install dependencies
pip install -e .

# 5. Verify everything works
python -m src.core.llm.test_connection
```

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — Full architecture description
- [PROGRESS.md](PROGRESS.md) — What's done, what's planned
- [config/README.md](config/README.md) — Configuration guide

## Agents

| Agent | Status | Description |
|-------|--------|-------------|
| Security Digest | 🔲 planned | Cybersecurity news digest |
| Job Hunter | 🔲 planned | CV adaptation, job applications |
| Calendar Sync | 🔲 planned | Google + O365 synchronization |
| Code Assistant | 🔲 planned | Coding help, API knowledge |
| Market Intel | 🔲 planned | Analytics, Gartner reports, etc. |
| Red Team Tools | 🔲 planned | Security training tools |

## How to Run Ingestion Worker

The Security Digest system includes a background worker that automatically fetches content from configured sources.

### Running Locally

```bash
# Start the worker with default settings
python -m src.workers.security_digest_worker

# Or use the console script
pa-worker

# With custom configuration via environment variables
WORKER_INTERVAL_SECONDS=120 WORKER_MAX_SOURCES=5 pa-worker
```

### Configuration

The worker can be configured via:

1. **Environment variables** (highest priority):
   - `WORKER_INTERVAL_SECONDS` — Sleep interval between fetch cycles (default: 300)
   - `WORKER_JITTER_SECONDS` — Random jitter to add to interval (default: 60)
   - `WORKER_MAX_SOURCES` — Max sources to fetch per cycle (default: 10)
   - `WORKER_LOG_LEVEL` — Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)

2. **Config file** `config/workers.yaml`:
   ```yaml
   security_digest_worker:
     interval_seconds: 300
     jitter_seconds: 60
     max_sources: 10
     log_level: INFO
   ```

### Running in Docker

Add to your `docker-compose.yaml`:

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

Then start with:
```bash
docker-compose up -d worker
```

### Stopping the Worker

The worker supports graceful shutdown:
- Press `Ctrl+C` when running in foreground
- `docker-compose stop worker` when running in Docker
- `kill -TERM <pid>` when running as a background process

The worker will complete the current fetch cycle and exit cleanly.

## Principles

1. **Atomicity** — Each component does one thing
2. **Interchangeability** — LLM providers can be swapped with one line
3. **Configuration separated from code** — Everything in YAML
4. **Verification** — Fighting hallucinations at every step
5. **Modularity** — Agents are independent of each other

## License

Private / Personal Use
