# 019: Daily Digest Scheduler

## Status
Accepted

## Date
2026-02-12

## Problem

Digests are only generated manually via the admin dashboard button or CLI. We need automatic daily generation at a configured time so the owner receives a digest without any manual action.

## Solution

### Scheduling approach
- A new worker (`src/workers/daily_digest_worker.py`) runs as a long-lived process.
- It reads the `digest_time` setting (interpreted as UTC, e.g. "08:00").
- A pure function `compute_next_run_utc(now_utc, digest_time_str)` calculates when to run next (today if not yet passed, tomorrow otherwise).
- The worker sleeps until the next run time, then calls `run_once()`.

### Idempotency strategy
- Before generating, the worker queries the `digests` table for today's date.
- If a digest already exists, the run is recorded as `status="skipped"` with `reason="already_exists"`.
- If a unique constraint violation (IntegrityError) occurs during generation (race condition), the run is recorded as `status="skipped"` with `reason="unique_conflict"`.
- This ensures exactly one digest per day regardless of how many workers are running.

### Job runs
Each scheduled attempt writes a `JobRun` with `job_name="digest_scheduler"`:
- `status="success"` with details: digest_date, digest_id, articles_total, notified, digest_time_utc
- `status="skipped"` with details: digest_date, reason
- `status="error"` with error_message and details: digest_date, digest_time_utc

### Telegram notification
- Reads the `telegram_notifications` setting.
- If enabled, the existing `DigestService.generate()` handles notification internally.
- If disabled, digest is still generated but no message is sent.
- The `notified` flag in job run details reflects whether notification was sent.

### Admin Operations
- The existing `/admin/operations` page gets a new "Digest Status" panel showing:
  - Settings summary (digest_time UTC, telegram_notifications)
  - Next scheduled run time
  - Latest digest info (date, article count, notified status)
  - Latest scheduler run (from job_runs)

## How to Test

Start the database:
```bash
docker-compose up -d postgres
```

Run the tests:
```bash
pytest tests/workers/test_daily_digest_worker.py tests/admin/test_routes.py -v
```

Run the scheduler manually:
```bash
python3 -m src.workers.daily_digest_worker
```
