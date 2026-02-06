#!/usr/bin/env bash
#
# Personal Assistant — Deploy Script
#
# Runs on the Hetzner server after CI pushes to master.
# Called by GitHub Actions via SSH: ~/personal_assistant/deploy/deploy.sh
#
# Steps:
# 1. Pull latest code
# 2. Install Python dependencies
# 3. Install Playwright browser (for browser fetcher)
# 4. Run database migrations
# 5. Restart services
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Personal Assistant Deploy ==="
echo "Project dir: $PROJECT_DIR"
echo "Date: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo ""

cd "$PROJECT_DIR"

# 1. Pull latest code
echo "--- Pulling latest code ---"
git pull origin master
echo ""

# 2. Install Python dependencies
echo "--- Installing Python dependencies ---"
pip3 install -e . --break-system-packages --quiet
echo "Python dependencies installed."
echo ""

# 3. Install Playwright browser
echo "--- Installing Playwright Chromium ---"
playwright install chromium
echo ""

# 4. Run database migrations
echo "--- Running database migrations ---"
alembic upgrade head
echo ""

# 5. Restart services
echo "--- Restarting services ---"
if systemctl is-active --quiet pa-worker 2>/dev/null; then
    sudo systemctl restart pa-worker
    echo "Restarted pa-worker"
fi

# Restart fetcher workers if the target exists
if systemctl list-units --type=target --all 2>/dev/null | grep -q pa-fetcher.target; then
    sudo systemctl restart pa-fetcher.target
    echo "Restarted pa-fetcher workers"
fi

echo ""
echo "=== Deploy complete ==="
