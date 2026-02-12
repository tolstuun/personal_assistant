# 016: Workers Config Loading

## Status
Accepted

## Date
2026-02-12

## Problem

The background worker (`src/workers/security_digest_worker.py`) tries to read its configuration from the main config like this:

```python
config.get("workers", {}).get("security_digest_worker", {})
```

But the config loader (`src/core/config/loader.py`) only loads these files: `llm`, `storage`, `telegram`, and `admin`. It never loads `workers.yaml` or `workers.example.yaml`, so the `"workers"` key is always missing from the merged config.

This means worker settings from YAML config files are silently ignored in real deployments. The worker falls back to hardcoded defaults or environment variables, which works but defeats the purpose of having YAML-based configuration.

## Solution

Add `workers.example.yaml` and `workers.yaml` to the config loader's file list, using the same example-then-override pattern as the other configs:

1. **`config/workers.example.yaml`** — committed to git, contains sensible defaults (no secrets)
2. **`config/workers.yaml`** — gitignored, for per-deployment overrides
3. **`src/core/config/loader.py`** — add both files to the `config_files` list
4. **`.gitignore`** — add `config/workers.yaml`

## How to Test

Run the tests:
```bash
pytest tests/core/config/test_loader.py -v
```

You should see all tests pass, including:
- `test_workers_config_loaded` — verifies workers config is loaded from example file
- `test_workers_yaml_overrides_example` — verifies workers.yaml overrides workers.example.yaml via deep merge
