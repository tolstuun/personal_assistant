# Decision 010: Admin Settings Page and Database-Driven Worker Configuration

**Date:** 2026-02-02
**Status:** Proposed
**Author:** Claude (AI Assistant)

## Problem

The current system has several configuration values hardcoded or in config files:
- Fetch interval is set via environment variable (`WORKER_INTERVAL_SECONDS`)
- Digest generation time is not configurable
- Telegram notification settings are in config files
- Digest sections are hardcoded

This makes it difficult for the non-technical owner to:
1. Adjust how often content is fetched
2. Change when daily digests are generated
3. Enable/disable notifications
4. Choose which sections appear in digests

We need a way to manage these settings through the admin UI.

## Solution

### 1. Settings Database Table

Create a key-value settings table with JSON value support:

```sql
CREATE TABLE settings (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

**Why key-value instead of columns:**
- Flexible: add new settings without schema migrations
- Simple: no need to define nullable columns for optional settings
- JSON values support complex types (arrays, objects)

**Default settings:**

| Key | Default Value | Description |
|-----|---------------|-------------|
| `fetch_interval_minutes` | `60` | How often to run the fetcher |
| `fetch_worker_count` | `3` | Number of parallel worker instances |
| `digest_time` | `"08:00"` | When to generate daily digest (24h format) |
| `telegram_notifications` | `true` | Whether to send Telegram notifications |
| `digest_sections` | `["security_news", "product_news", "market"]` | Which sections to include |

### 2. Admin Settings Page

New route at `/admin/settings` with:
- List view showing all settings with current values
- Edit form for each setting type (number, time, boolean, multi-select)
- Reset to default option

### 3. Worker Configuration

Modify the background worker to:
1. Read `fetch_interval_minutes` from database on startup
2. Re-read settings periodically (every 5 minutes) to pick up changes
3. Fall back to environment variable / config file if database unavailable

### 4. Multi-Worker Support

The system supports running multiple parallel workers for faster content ingestion:

**Why multiple workers:**
- Faster processing of many sources
- Better utilization of network and database capacity
- Resilience: if one worker crashes, others continue

**How it works:**
- `fetch_worker_count` setting controls target number of workers
- Each worker uses `SELECT ... FOR UPDATE SKIP LOCKED` to claim sources
- No duplicate work: workers automatically skip sources being processed
- Systemd template unit (`pa-fetcher@.service`) supports N instances

**Worker manager script:**
```bash
pa-worker-manager start   # Start workers based on fetch_worker_count
pa-worker-manager stop    # Stop all workers
pa-worker-manager reload  # Adjust count to match setting
pa-worker-manager status  # Show running workers
```

**Manual control:**
```bash
systemctl start pa-fetcher@{1..3}   # Start workers 1, 2, 3
systemctl stop pa-fetcher@2         # Stop worker 2
journalctl -u 'pa-fetcher@*' -f     # Follow all worker logs
```

### Architecture

```
src/core/models/
└── settings.py           # Setting model

src/admin/routes/
└── settings.py           # CRUD routes for settings

src/admin/templates/settings/
├── list.html             # Settings list page
└── _setting_row.html     # Individual setting row

src/workers/
├── security_digest_worker.py  # Individual worker process
└── worker_manager.py          # Multi-worker orchestration

deploy/
├── pa-fetcher@.service   # Systemd template unit
└── pa-fetcher.target     # Target for all workers
```

### Model Design

```python
class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow_naive, onupdate=utcnow_naive, nullable=False
    )
```

### Settings Service

A service layer to manage settings with defaults:

```python
class SettingsService:
    DEFAULTS = {
        "fetch_interval_minutes": 60,
        "digest_time": "08:00",
        "telegram_notifications": True,
        "digest_sections": ["security_news", "product_news", "market"],
    }

    async def get(self, key: str) -> Any:
        """Get setting value, falling back to default."""

    async def set(self, key: str, value: Any) -> None:
        """Set setting value (upsert)."""

    async def get_all(self) -> dict[str, Any]:
        """Get all settings with defaults applied."""

    async def reset(self, key: str) -> None:
        """Reset setting to default value."""
```

### Worker Integration

```python
async def run_worker():
    settings_service = SettingsService()

    while not shutdown_event.is_set():
        # Re-read settings to pick up changes
        interval = await settings_service.get("fetch_interval_minutes")

        # Fetch sources
        stats = await manager.fetch_due_sources(max_sources=config.max_sources)

        # Sleep using database-configured interval
        await asyncio.sleep(interval * 60 + jitter)
```

## How to Test

### Prerequisites
```bash
docker-compose up -d postgres
```

### Run Tests
```bash
pytest tests/admin/test_settings.py -v
pytest tests/core/models/test_settings.py -v
```

### Manual Testing
```bash
python run.py
# Visit http://localhost:8000/admin/settings
# Login with admin password
# Change fetch_interval_minutes to 5
# Restart worker, verify it runs every 5 minutes
```

### Verify Database
```bash
docker-compose exec postgres psql -U assistant -d assistant \
  -c "SELECT * FROM settings;"
```

## Alternatives Considered

### 1. Config File Only
- **Pro:** Simple, no database changes
- **Con:** Requires server access to change, can't change at runtime

### 2. Environment Variables Only
- **Pro:** Standard approach
- **Con:** Requires restart, no UI for non-technical user

### 3. Separate Settings Table per Type
- **Pro:** Type safety at database level
- **Con:** More complex schema, migrations for new settings

## Security Considerations

1. **Admin auth required** — All settings routes protected by admin middleware
2. **Input validation** — Validate setting values before saving
3. **Audit logging** — Log setting changes (future enhancement)

## Migration Path

1. Create `settings` table (no data migration needed)
2. Worker reads from DB, falls back to env vars
3. Admin UI for managing settings
4. Eventually remove env var fallback (optional)

## Future Improvements

1. **Setting categories** — Group settings by area (fetcher, digest, notifications)
2. **Setting history** — Track who changed what and when
3. **Import/export** — Backup and restore settings
4. **Validation rules** — Per-setting validation (min/max, regex, etc.)
