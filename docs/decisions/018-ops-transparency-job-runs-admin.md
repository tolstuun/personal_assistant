# 018: Ops Transparency — Fetch Cycle Logging & Admin Operations Page

## Status
Accepted

## Date
2026-02-12

## Problem

The fetch worker runs continuously in the background, but there's no way to see:
- When the last fetch cycle ran
- Whether it succeeded or failed
- How many sources/articles were processed
- What errors occurred

Without this visibility, problems go unnoticed until someone manually checks logs on the server. The `job_runs` table (added in PR1/ADR 017) exists but nothing writes to it yet, and there's no UI to view it.

## Solution

Two changes in this PR:

### 1. Instrument the fetch worker
Each fetch cycle in `security_digest_worker.py` now records a `JobRun`:
- **Before fetch:** creates a row with `job_name="fetch_cycle"`, `status="running"`
- **After success:** updates with `status="success"` and stats (sources checked, articles found, errors, etc.)
- **On exception:** updates with `status="error"` and the error message

Job run logging is wrapped in try/except so it never crashes the worker.

### 2. Admin Operations page
New page at `/admin/operations` showing:
- **Latest Fetch Cycle card** — status, timing, duration, key stats
- **Recent Job Runs table** — last 20 runs (all job types) sorted newest first

### Deferred to PR3
- Daily digest scheduler (will also write job_runs)
- Job run cleanup/retention policy
- Alerting on repeated failures

## How to Test

Start the database:
```bash
docker-compose up -d postgres
```

Run the tests:
```bash
pytest tests/workers/test_security_digest_worker.py tests/admin/test_routes.py -v
```
