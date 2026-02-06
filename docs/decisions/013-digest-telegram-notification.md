# 013: Digest Telegram Notification

## Status
Accepted

## Problem
When a digest is generated, the owner has no way to know unless they check the admin UI or the filesystem. We need to proactively notify them via Telegram when a new digest is ready.

## Solution

### TelegramNotifier (`src/core/services/notifier.py`)
A lightweight service for sending Telegram notifications, separate from the full `TelegramBot` class:

- Uses `telegram.Bot` directly (just needs token + chat IDs)
- Reads config from `config/telegram.yaml` via `get_config()`
- Sends to all `allowed_users` from the telegram config
- Never crashes — returns True/False, logs errors

### Integration with DigestService
After digest creation (step 8 in `generate()`), the service:
1. Checks `telegram_notifications` setting (boolean, default True)
2. If enabled, sends notification with: date, article count, link to HTML
3. Updates `digest.notified_at` timestamp on success
4. Logs warning on failure but doesn't block digest creation

### Why not modify TelegramBot?
The existing `TelegramBot` class requires an `Orchestrator` and is designed for webhook request/response. A notification is a different concern — fire-and-forget, no orchestrator needed. Keeping them separate follows the one-component-one-responsibility principle.

## Message Format
```
Security Digest — February 5, 2026

15 articles across 3 sections

View digest: https://aioid.vip/digests/digest-2026-02-05.html
```

## How to Test

```bash
# Unit tests
pytest tests/core/services/test_notifier.py tests/core/services/test_digest.py -v

# Manual: generate a digest (will send notification if telegram_notifications is enabled)
python -m src.core.services.digest --generate

# Disable notifications via admin UI: Settings > Telegram Notifications > Disabled
```
