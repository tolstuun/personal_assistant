# 017: Job Run Logging

## Status
Accepted

## Date
2026-02-12

## Problem

We have no visibility into when background jobs run, whether they succeed or fail, or how long they take. When something goes wrong (e.g. the fetch worker silently errors), there's no record to investigate. As we add more scheduled jobs (daily digest, cleanup), this blind spot gets worse.

We need a database table to record each job execution with its outcome, duration, and any error messages. This is the foundation for:
- An admin "Job History" page (future PR)
- Scheduler tracking (future PR)
- Alerting on repeated failures (future PR)

## Solution

Add a `job_runs` table and a small `JobRunService` to record job executions:

1. **`src/core/models/job_runs.py`** — SQLAlchemy model with columns: id (UUID), job_name, status (running/success/error/skipped), started_at, finished_at, details (JSONB for small stats), error_message.

2. **`src/core/services/job_runs.py`** — Service with three methods:
   - `start(job_name)` — creates a "running" row, returns the run ID
   - `finish(run_id, status, ...)` — sets the final status, finished_at, and optional details/error
   - `get_latest(job_name)` — returns the most recent run for a job

3. **Alembic migration 004** — creates the table with indexes on `job_name` and `started_at`.

This PR does NOT add any admin pages or modify any workers. It only adds the data layer.

## How to Test

Start the database first:
```bash
docker-compose up -d postgres
```

Then run the tests:
```bash
pytest tests/core/services/test_job_runs.py -v
```

You should see all tests pass. These tests require a running PostgreSQL instance (they're integration tests).
