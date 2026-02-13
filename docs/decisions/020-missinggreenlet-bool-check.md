# 020: Fix MissingGreenlet on SQLAlchemy model truthiness checks

## Status
Accepted

## Date
2026-02-13

## Problem

`/admin/operations` returns 500 with `sqlalchemy.exc.MissingGreenlet` in production. The previous fix (PR #25) replaced `latest_digest.articles` access with an explicit count query, but missed a subtler issue: even `if latest_digest:` evaluates `bool()` on the SQLAlchemy model, which can trigger lazy-loading of relationships in async mode.

This same pattern (`if obj:` / `if not obj:`) exists in 9 places across 4 files, all on variables holding SQLAlchemy model instances returned by `scalar_one_or_none()`.

## Root Cause

In async SQLAlchemy (with asyncpg), calling `bool()` on a mapped model instance may trigger implicit lazy-loads of unloaded relationships. This raises `MissingGreenlet` because there's no synchronous greenlet context to execute the SQL.

The safe pattern is `if obj is not None:` / `if obj is None:`, which checks identity without invoking any SQLAlchemy machinery.

## Solution

Replace all bare truthiness checks on SQLAlchemy model objects with explicit `is None` / `is not None` checks:

### Files changed

1. `src/admin/routes/operations.py` (1 instance)
2. `src/admin/routes/sources.py` (4 instances)
3. `src/admin/routes/categories.py` (3 instances)
4. `src/core/primitives/fetchers/manager.py` (2 instances)

### Deploy script fix

The deploy script (`deploy/deploy.sh`) only restarts worker processes, not the web server (uvicorn). Added `pa-web` service restart so code changes to admin routes take effect on deploy.

## How to Test

```bash
pytest tests/admin/test_routes.py -v
ruff check src/admin/routes/ src/core/primitives/fetchers/manager.py
```
