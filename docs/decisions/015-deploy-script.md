# 015: Version-Controlled Deploy Script

## Status
Accepted

## Problem
The deploy script (`deploy.sh`) previously lived only on the Hetzner server and only ran `git pull`. This meant:
- New dependencies (like Playwright Chromium) had to be installed manually after deploy
- Database migrations had to be run manually
- No single source of truth for the deployment process
- Easy to forget a step after adding new features

## Solution
Create `deploy/deploy.sh` in the repository that handles the full deployment lifecycle:

1. **Git pull** — fetch latest code from master
2. **Python dependencies** — `pip3 install -e . --break-system-packages`
3. **Playwright browser** — `playwright install chromium` (for browser fetcher)
4. **Database migrations** — `alembic upgrade head`
5. **Service restart** — restart systemd services

The CI deploy step (`ci-cd.yml`) is updated to call the new path: `~/personal_assistant/deploy/deploy.sh`.

### Why `--break-system-packages`?
The Hetzner server uses system Python (no virtualenv). The `--break-system-packages` flag is needed on modern Debian/Ubuntu systems that enforce PEP 668.

### Why version-controlled?
- Single source of truth for the deploy process
- Changes to deploy are reviewed in PRs like any other code
- New team members can see exactly how deployment works

## How to Test
```bash
# The deploy runs automatically on merge to master via CI
# To run manually on the server:
ssh user@server "~/personal_assistant/deploy/deploy.sh"
```
