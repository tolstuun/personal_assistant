# Decision 009: Scalable Article Persistence with Bulk UPSERT

**Date:** 2026-02-02
**Status:** Accepted
**Author:** Claude (AI Assistant)

## Problem

The original `FetcherManager._save_articles()` implementation used N+1 queries for URL deduplication:

```python
# OLD CODE (N+1 pattern)
for article in articles:
    # One SELECT per article to check for duplicates
    existing = await session.execute(
        select(Article).where(Article.url == article.url)
    )
    if existing.scalar_one_or_none():
        stats["duplicate"] += 1
        continue

    # One INSERT per article
    session.add(Article(...))
```

### Why N+1 Doesn't Scale

1. **Query overhead**: For N articles, we execute N SELECT queries + N INSERT queries = 2N database round-trips
2. **Latency accumulation**: Each query adds network latency (~1-5ms locally, more in production)
3. **Example scenario**:
   - 50 articles from a source
   - 100 queries (50 SELECT + 50 INSERT)
   - At 2ms per query = 200ms just for database I/O
   - With bulk insert: 1 query = 2ms

### Race Conditions Under Concurrency

Two workers processing different sources could return articles with the same URL:

```
Worker 1: SELECT WHERE url='A' → not found
Worker 2: SELECT WHERE url='A' → not found
Worker 1: INSERT url='A' → success
Worker 2: INSERT url='A' → UNIQUE VIOLATION ERROR!
```

This causes:
- Transaction rollback in Worker 2
- Source not marked as fetched (requires retry)
- Unnecessary error handling complexity

## Solution

Replace per-article deduplication with Postgres `INSERT ... ON CONFLICT DO NOTHING`:

```python
# NEW CODE (bulk upsert)
stmt = (
    pg_insert(Article)
    .values(rows_to_insert)  # List of all article dicts
    .on_conflict_do_nothing(index_elements=["url"])
    .returning(Article.url)
)

result = await session.execute(stmt)
inserted_urls = result.scalars().all()

inserted = len(inserted_urls)
duplicates = len(rows_to_insert) - inserted
```

### Why ON CONFLICT DO NOTHING is Correct

1. **Atomicity**: The entire batch is processed in a single statement
2. **Concurrency safety**: Postgres handles the race condition at the database level
3. **No errors on duplicates**: Conflicting rows are silently skipped (not errored)
4. **Deterministic behavior**: Exactly one row will exist after any number of concurrent inserts

### How RETURNING Provides Accurate Stats

Using `RETURNING Article.url`:
- Only URLs that were actually inserted are returned
- Duplicates (conflicts) don't appear in the result
- `inserted = len(returned_urls)` is always correct
- `duplicates = attempted - inserted` is always correct

**Why not use rowcount?**
- `rowcount` may include rows affected by triggers
- `rowcount` behavior varies across database drivers
- `RETURNING` is explicit and unambiguous

## Implementation Details

### Filtering Pipeline (Unchanged)

The filtering semantics remain identical:

1. **Date filter** (cheap, no DB): Articles older than cutoff are skipped
2. **Keyword filter** (cheap, no DB): Articles not matching keywords are skipped
3. **Deduplication** (now in bulk): Handled by ON CONFLICT DO NOTHING

```python
# First pass: collect rows that pass date/keyword filters
for article in articles:
    if not self._is_recent_enough(article, cutoff_date):
        stats["old"] += 1
        continue

    if not self._matches_keywords(article, source):
        stats["filtered"] += 1
        continue

    rows_to_insert.append({...})

# Second pass: bulk insert with dedup
stmt = pg_insert(Article).values(rows_to_insert).on_conflict_do_nothing(...)
```

### Stats Semantics

| Field | Meaning |
|-------|---------|
| `filtered` | Articles removed by keyword filter (unchanged) |
| `old` | Articles removed by date filter (unchanged) |
| `saved` | Articles actually inserted (from RETURNING count) |
| `duplicate` | URL conflicts (attempted - inserted) |

### Error Handling

```python
try:
    result = await session.execute(stmt)
    # ... calculate stats ...
    await session.flush()
except Exception as e:
    logger.error(f"Bulk insert failed: {e}")
    await session.rollback()
    raise
```

If the bulk insert fails for any reason (e.g., constraint violation on other fields), the entire batch is rolled back. This maintains transactional consistency.

## Performance Characteristics

### Query Reduction

| Scenario | Old (N+1) | New (Bulk) |
|----------|-----------|------------|
| 10 articles, 0 duplicates | 20 queries | 1 query |
| 50 articles, 10 duplicates | 100 queries | 1 query |
| 100 articles, 50 duplicates | 200 queries | 1 query |

### Latency Improvement

For 50 articles at 2ms/query:
- Old: ~100ms (50 SELECT + 50 INSERT)
- New: ~2ms (1 bulk INSERT)

**50x improvement** in database I/O time.

### Memory Trade-off

The new approach builds a list of all article dicts in memory before inserting:
- For 100 articles with 1KB content each: ~100KB memory
- Acceptable trade-off for performance gain
- If memory becomes a concern, batch in chunks of 500-1000

## Testing Strategy

Two new integration tests verify the implementation:

### test_bulk_insert_counts_duplicates

- Fetcher returns 2 articles with the **same URL** in one batch
- Verifies: DB has exactly 1 article, stats show 1 inserted + 1 duplicate

### test_concurrent_insert_same_url

- Two workers fetch from different sources, both return the **same URL**
- Workers run concurrently with `asyncio.gather()`
- Verifies: DB has exactly 1 article, no unique violation errors, combined stats show 1 insert + 1 duplicate

Both tests use:
- Real Postgres database (test instance)
- Monkeypatched fetchers (no network I/O)
- Sleep delays to create overlap in concurrent test

## Alternatives Considered

### Alternative 1: Batch SELECT then INSERT

```python
# Check all URLs at once
existing_urls = SELECT url FROM articles WHERE url IN (...)

# Filter out existing, then insert new
for article in articles:
    if article.url not in existing_urls:
        INSERT article
```

**Problems**:
- Still has race condition between SELECT and INSERT
- Two queries instead of one
- More complex code

### Alternative 2: INSERT ... ON CONFLICT DO UPDATE

```python
INSERT INTO articles (url, ...) VALUES (...)
ON CONFLICT (url) DO UPDATE SET fetched_at = EXCLUDED.fetched_at
```

**Problems**:
- Updates existing rows unnecessarily
- Triggers index updates on every conflict
- Changes semantics (first fetch wins vs. last fetch wins)

**Decision**: ON CONFLICT DO NOTHING is simpler and matches our desired semantics (first article wins).

### Alternative 3: Application-level distributed lock

```python
with redis_lock(f"article:{article.url}"):
    if not exists_in_db(article.url):
        insert(article)
```

**Problems**:
- Requires Redis dependency
- Additional failure mode (lock timeout)
- More complex deployment
- Database-level locking is sufficient

**Decision**: Let Postgres handle concurrency - it's designed for this.

## Trade-offs

| Aspect | Old Approach | New Approach |
|--------|--------------|--------------|
| Query count | O(N) | O(1) |
| Concurrency safety | Race condition | Safe |
| Memory usage | O(1) per article | O(N) for batch |
| Code complexity | Simple loop | Bulk insert logic |
| Debugging | Easy to trace | One statement |
| Partial failures | Per-article | Whole batch |

## Future Options

### Content Hashing

Current deduplication is URL-based. Future enhancement could add content hashing:

```python
# Detect same content at different URLs
content_hash = hashlib.sha256(article.content).hexdigest()[:16]

INSERT INTO articles (url, content_hash, ...)
ON CONFLICT (url) DO NOTHING
ON CONFLICT (content_hash) DO NOTHING  -- Requires separate constraint
```

**Trade-off**: Adds complexity, may have false positives on boilerplate content.

### Chunked Batching

For very large batches (>1000 articles):

```python
CHUNK_SIZE = 500
for i in range(0, len(rows), CHUNK_SIZE):
    chunk = rows[i:i + CHUNK_SIZE]
    stmt = pg_insert(Article).values(chunk).on_conflict_do_nothing(...)
    await session.execute(stmt)
```

**Trade-off**: More queries, but bounded memory usage.

## Migration Path

This change is **backward compatible**:
- No database schema changes required
- Article.url already has unique constraint
- No new dependencies
- Existing data unaffected

**Rollout**:
1. Deploy new code
2. Workers automatically use new approach
3. Monitor for any unexpected behavior
4. Rollback is simple (just revert code)

## References

- [PostgreSQL INSERT ... ON CONFLICT](https://www.postgresql.org/docs/current/sql-insert.html#SQL-ON-CONFLICT)
- [SQLAlchemy Postgres Dialect Insert](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#insert-on-conflict-upsert)
- [PostgreSQL RETURNING Clause](https://www.postgresql.org/docs/current/dml-returning.html)
