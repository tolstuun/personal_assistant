# Decision 008: Due Source Selection and Multi-Worker Safety

**Date:** 2026-01-30
**Status:** Accepted
**Author:** Claude (AI Assistant)

## Problem

The original `FetcherManager.fetch_due_sources()` implementation had two critical issues that prevented it from working correctly in production:

### Issue 1: LIMIT Before Due-Check

The original code applied `.limit(max_sources)` in SQL before checking if sources were actually due:

```python
# OLD CODE (incorrect)
stmt = (
    select(Source)
    .where(Source.enabled.is_(True))
    .order_by(Source.last_fetched_at.asc().nullsfirst())
    .limit(max_sources)  # ⚠️ Limit BEFORE checking due status
)
result = await session.execute(stmt)
sources = result.scalars().all()

for source in sources:
    # Check if source is due (in Python)
    if source.last_fetched_at is not None:
        next_fetch = source.last_fetched_at + timedelta(minutes=source.fetch_interval_minutes)
        if next_fetch > now:
            continue  # Skip this source
```

**Why this is wrong:**
- The SQL query selects the 10 oldest sources (by `last_fetched_at`)
- But many of these might not be due yet
- The Python loop skips non-due sources but doesn't fetch additional ones
- Result: Can return 0 fetched sources even when other sources are due

**Example scenario:**
- 100 sources total
- 5 oldest sources were fetched 30 minutes ago (60-minute interval → not due)
- 10 sources were last fetched 2 hours ago (due)
- Query returns the 5 oldest + 5 of the due ones
- Worker skips the 5 not-due, fetches only 5 instead of 10

### Issue 2: No Multi-Worker Safety

Multiple workers could select and process the same sources simultaneously:

```python
# Worker 1 and Worker 2 both running
Worker 1: SELECT * FROM sources WHERE ... LIMIT 10
Worker 2: SELECT * FROM sources WHERE ... LIMIT 10
# Both get the same 10 sources!

Worker 1: processes source A
Worker 2: processes source A (duplicate work!)
```

**Consequences:**
- Wasted resources (fetching same content twice)
- Potential data inconsistencies
- Violates fetch interval constraints (source is "over-fetched")
- Race conditions on `last_fetched_at` updates

## Solution

### Part A: SQL-Based Due Selection

Move the due-check into the SQL query using Postgres interval arithmetic:

```python
# Define due condition in SQL
now_utc = func.timezone("utc", func.now())
interval_1m = literal_column("interval '1 minute'")
due_when = or_(
    Source.last_fetched_at.is_(None),
    Source.last_fetched_at <= now_utc - (Source.fetch_interval_minutes * interval_1m),
)

stmt = (
    select(Source)
    .options(selectinload(Source.category))
    .where(Source.enabled.is_(True), due_when)  # ✅ Due check in SQL
    .order_by(Source.last_fetched_at.asc().nullsfirst())
    .limit(1)  # Fetch one at a time (for locking)
)
```

**SQL generated:**
```sql
SELECT * FROM sources
WHERE enabled = true
  AND (
    last_fetched_at IS NULL
    OR last_fetched_at <= timezone('utc', now()) - (fetch_interval_minutes * interval '1 minute')
  )
ORDER BY last_fetched_at ASC NULLS FIRST
LIMIT 1
```

**Why per-row interval is correct:**
- Each source has its own `fetch_interval_minutes` (some 60, some 120, etc.)
- The condition `last_fetched_at <= (now - fetch_interval_minutes * 1 minute)` evaluates per row
- Postgres optimizes this efficiently

**Benefits:**
- Only due sources are selected
- Database does the filtering (more efficient than Python)
- No wasted iterations

### Part B: Multi-Worker Safety with SKIP LOCKED

Use `SELECT ... FOR UPDATE SKIP LOCKED` to "claim" sources atomically:

```python
for _ in range(max_sources):
    async with db.session() as session:
        stmt = (
            select(Source)
            .where(Source.enabled.is_(True), due_when)
            .order_by(Source.last_fetched_at.asc().nullsfirst())
            .with_for_update(skip_locked=True)  # ✅ Lock row, skip if already locked
            .limit(1)
        )

        result = await session.execute(stmt)
        source = result.scalar_one_or_none()

        if not source:
            break  # No more due sources

        # Lock is held until commit/rollback
        await self._fetch_source(session, source)
```

**How SKIP LOCKED works:**
1. Worker 1 executes `SELECT ... FOR UPDATE` → acquires lock on row A
2. Worker 2 executes same query → sees row A is locked, **skips it** (SKIP LOCKED), selects row B instead
3. Worker 1 completes, commits → releases lock on row A
4. Worker 2 completes, commits → releases lock on row B

**SQL generated:**
```sql
SELECT * FROM sources
WHERE enabled = true AND (...)
ORDER BY last_fetched_at ASC NULLS FIRST
LIMIT 1
FOR UPDATE SKIP LOCKED;
```

**Without SKIP LOCKED (wrong):**
- Worker 2 would **wait** for Worker 1 to release the lock
- All workers serialize → no concurrency
- Or worse, if we used `NOWAIT`, Worker 2 would get an error

**Benefits:**
- Workers never process the same source
- No waiting (workers skip locked rows and find available ones)
- Maximum concurrency
- No deadlocks

### Part C: One Source at a Time

The new implementation processes sources one at a time instead of batching:

```python
for _ in range(max_sources):
    async with db.session() as session:  # New session per source
        # Select one source
        # Fetch from it
        # Commit (releases lock)
```

**Why one at a time:**
- Minimizes lock contention (lock held only during single source fetch)
- Other workers can pick up remaining sources immediately
- Simplifies error handling (rollback one source, continue to next)

**Tradeoff: Lock Held During Network I/O**

The lock is held while fetching content from the source URL (network I/O):

```python
source = await session.execute(SELECT ... FOR UPDATE)  # Lock acquired
articles = await fetcher.fetch_articles(source.url)     # Network I/O (seconds)
await session.commit()                                  # Lock released
```

**Why we accept this:**
- Alternative 1: Select sources, release locks, then fetch
  - Problem: Another worker could claim the same source before we fetch
  - Requires additional "claimed" state or distributed lock
- Alternative 2: Use a queue (Celery, Redis queue)
  - Problem: Adds infrastructure complexity
  - Overkill for current needs
- Current approach is simple and correct
- Network I/O is relatively fast (2-5 seconds per source)
- Lock contention is minimal with SKIP LOCKED

**Future improvement:** Add a `claimed_at` column or `in_progress` status:
```python
# Future: claim without holding lock
UPDATE sources SET claimed_at = now() WHERE id = ... AND claimed_at IS NULL
# Then fetch without lock
# Then update last_fetched_at and clear claimed_at
```

This would allow claiming many sources, releasing locks, then fetching. But it adds complexity and state management. Not needed for current scale.

## Implementation Details

### Error Handling and Lock Release

When an error occurs during fetch, we must explicitly rollback to release the lock:

```python
try:
    source_stats = await self._fetch_source(session, source)
    stats.sources_fetched += 1
    # ... update stats ...
except Exception as e:
    logger.error(f"Error fetching {source.name}: {e}")
    stats.errors.append(f"{source.name}: {str(e)}")
    await session.rollback()  # ✅ Release lock immediately
```

Without explicit rollback:
- Lock remains held until session context exits
- Other workers can't process this source
- Worker wastes time holding the lock

With explicit rollback:
- Lock released immediately
- Source becomes available for retry by another worker (or this worker on next iteration)
- Current worker continues to next source

### Stats Semantics

Updated semantics for `FetchStats` fields:

- **`sources_checked`**: Number of sources successfully **claimed** (locked) for processing
  - Incremented after `SELECT ... FOR UPDATE` returns a source
  - Represents how many sources this worker attempted

- **`sources_fetched`**: Number of sources where fetch **completed successfully**
  - Incremented after `_fetch_source()` returns without exception
  - Represents how many sources were actually updated

Example:
- Worker claims 5 sources (sources_checked = 5)
- 2 sources fail due to network errors
- 3 sources succeed (sources_fetched = 3)
- 2 errors recorded in stats.errors

## Testing Strategy

### Integration Tests with Real Database

The new implementation includes comprehensive integration tests against a real Postgres database:

1. **Due filtering correctness** (`test_due_filtering_correctness`)
   - Creates sources: due (NULL), due (old), not due (recent), disabled (old)
   - Verifies only enabled + due sources are fetched
   - Verifies not-due and disabled sources are untouched

2. **max_sources limit** (`test_max_sources_limit`)
   - Creates 3 due sources
   - Fetches with max_sources=2
   - Verifies exactly 2 sources are updated

3. **Multi-worker safety** (`test_multi_worker_safety`)
   - Creates 2 due sources
   - Runs 2 workers concurrently with max_sources=1 each
   - Adds delay in fetch to hold locks
   - Verifies both sources are processed (not the same one twice)
   - Verifies SKIP LOCKED prevents duplicate work

4. **Error handling and lock release** (`test_error_handling_releases_lock`)
   - Creates 2 due sources
   - First source fails (raises exception)
   - Verifies second source is still processed
   - Verifies lock is released on error

### Test Infrastructure

- `tests/core/primitives/fetchers/conftest.py`: Database fixture with table creation/cleanup
- Monkeypatches `get_db()` to use test database
- Monkeypatches `fetch_articles()` to avoid network I/O
- Uses `clean_database` fixture to isolate tests

## Performance Characteristics

### Database Load

**Old approach:**
- 1 query to select N sources
- N queries to check duplicate articles
- N queries to insert articles
- N queries to update last_fetched_at
- **Total: ~1 + 3N queries**

**New approach:**
- N queries to select 1 source each (with lock)
- N queries to check duplicate articles
- N queries to insert articles
- N queries to update last_fetched_at (inside _fetch_source)
- **Total: ~4N queries**

**Tradeoff:**
- More queries (4N vs 3N+1)
- But: Each source is committed independently (no large transaction)
- But: Locks released promptly (better concurrency)
- But: Failures isolated (one source failure doesn't rollback others)

For N=10 sources: ~40 queries vs ~31 queries. Acceptable tradeoff for correctness and safety.

### Concurrency Scaling

With M workers and N due sources:
- Old: Workers often process same sources (wasted work)
- New: Workers process different sources (no waste)

**Example:** 100 due sources, 5 workers, max_sources=10 each:
- Old: 5 workers × 10 sources = 50 fetches, but with overlap → maybe 35 unique sources fetched
- New: 5 workers × 10 sources = 50 unique sources fetched (no overlap)

**Result:** Better resource utilization, faster overall completion.

## Alternatives Considered

### Alternative 1: Batch Select with SKIP LOCKED

```python
# Select multiple sources at once
stmt = select(Source).where(...).with_for_update(skip_locked=True).limit(max_sources)
sources = await session.execute(stmt)

for source in sources:
    await _fetch_source(session, source)
```

**Problem:**
- All locks held until end of batch
- Long-running transaction (minutes if max_sources=10)
- Locks not released incrementally
- Worse concurrency

**Rejected** in favor of one-at-a-time.

### Alternative 2: Optimistic Locking with claimed_at

```python
# Claim sources without lock
UPDATE sources SET claimed_at = now(), claimed_by = worker_id
WHERE id IN (SELECT id FROM sources WHERE enabled AND due AND claimed_at IS NULL LIMIT 10)

# Fetch without lock
for source_id in claimed_ids:
    source = SELECT * FROM sources WHERE id = source_id
    articles = await fetch_articles(source.url)
    UPDATE sources SET last_fetched_at = now(), claimed_at = NULL WHERE id = source_id
```

**Advantages:**
- No locks held during network I/O
- Can claim many sources at once

**Disadvantages:**
- Requires new `claimed_at` and `claimed_by` columns
- Requires cleanup of stale claims (worker crashes → claimed_at stuck)
- More complex state management
- Overkill for current scale

**Decision:** Keep it simple for now, add this if needed later.

### Alternative 3: External Queue (Celery, Redis Queue)

Move scheduling to a dedicated queue system:
- Producer: Scans for due sources, pushes to queue
- Workers: Pull from queue, fetch, update DB

**Advantages:**
- Proven infrastructure
- Visibility into queue depth
- Retries, dead letter queues

**Disadvantages:**
- More services to manage
- More failure modes
- More complex deployment
- Overkill for current needs

**Decision:** Not needed yet. Current solution is sufficient.

## Migration Path

This change is **backward compatible**:
- No database schema changes
- No new dependencies
- Existing sources work as-is
- Existing worker processes can be updated independently

**Rollout plan:**
1. Deploy new code
2. Restart workers one at a time
3. Monitor for any issues
4. If problems, rollback is easy (no schema changes)

## Success Criteria

The implementation is successful if:
- ✅ Only due sources are fetched
- ✅ max_sources limit is respected
- ✅ Multiple concurrent workers don't duplicate work
- ✅ Errors during fetch don't prevent other sources from being processed
- ✅ Integration tests pass consistently
- ✅ No increase in database errors or lock timeouts in production

## Future Improvements

1. **Add claimed_at column** for longer-running fetches
   - When fetch time exceeds reasonable lock duration (>30s)
   - Requires stale claim cleanup logic

2. **Add Prometheus metrics**
   - `sources_claimed_total` (counter)
   - `sources_fetched_total` (counter)
   - `sources_fetch_duration_seconds` (histogram)
   - `sources_fetch_errors_total` (counter)

3. **Add priority field**
   - Some sources are more important
   - ORDER BY priority DESC, last_fetched_at ASC

4. **Adaptive fetch_interval_minutes**
   - Increase interval if source rarely updates
   - Decrease interval if source updates frequently
   - Learn optimal interval per source

## References

- [Postgres FOR UPDATE SKIP LOCKED documentation](https://www.postgresql.org/docs/current/sql-select.html#SQL-FOR-UPDATE-SHARE)
- [SQLAlchemy with_for_update documentation](https://docs.sqlalchemy.org/en/20/core/selectable.html#sqlalchemy.sql.expression.GenerativeSelect.with_for_update)
- Blog: [Postgres Job Queues with SKIP LOCKED](https://www.2ndquadrant.com/en/blog/what-is-select-skip-locked-for-in-postgresql-9-5/)
