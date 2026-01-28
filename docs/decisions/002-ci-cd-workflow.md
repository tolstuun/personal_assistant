# Decision 002: CI/CD Workflow

**Date:** 2026-01-28
**Status:** Proposed
**Author:** Claude (AI Assistant)

## Problem

The project needs automated testing and deployment to:
- Catch bugs before they reach production (run linting and tests on every PR)
- Automate deployment to Hetzner server when changes are merged to master
- Ensure consistent quality across all contributions

Currently there is no CI/CD pipeline. Manual testing and deployment is error-prone.

## Solution

### GitHub Actions Workflow

Create `.github/workflows/ci-cd.yml` that:

1. **Triggers on:**
   - Push to `master` branch
   - Pull requests targeting any branch

2. **For all triggers (test job):**
   - Checkout code
   - Set up Python 3.11
   - Install dependencies from `requirements.txt`
   - Run `ruff check .` for linting
   - Run `pytest` for tests

3. **For master only (deploy job):**
   - Only runs after tests pass
   - SSH into Hetzner server
   - Execute `~/personal_assistant/deploy.sh`

### Secrets Required

These GitHub secrets must be configured in the repository settings:

| Secret | Description |
|--------|-------------|
| `HETZNER_SSH_KEY` | Private SSH key for server access |
| `HETZNER_HOST` | Server hostname or IP address |
| `HETZNER_USER` | SSH username on the server |

### Workflow Structure

```yaml
name: CI/CD

on:
  push:
    branches: [master]
  pull_request:

jobs:
  test:
    # Runs on all triggers
    # Checkout, Python setup, install deps, ruff, pytest

  deploy:
    # Runs only on master push
    # Needs: test (waits for tests to pass)
    # SSH to Hetzner and run deploy.sh
```

### Security Considerations

- SSH key is stored as a GitHub secret (never in code)
- Deploy job only runs on master, not on PRs (prevents unauthorized deployments)
- Using `appleboy/ssh-action` which is a well-maintained GitHub Action for SSH

## How to Test

### Test the Workflow Locally (dry run)

You can't fully test GitHub Actions locally, but you can verify the individual steps:

```bash
# Install dependencies
pip install -r requirements.txt

# Run linting (should pass)
ruff check .

# Run tests (should pass)
pytest
```

### Test on GitHub

1. Create a pull request - should trigger the test job only
2. Merge to master - should trigger test job, then deploy job

### Verify Deployment

After merging to master:
1. Check the Actions tab in GitHub for green checkmarks
2. SSH into the Hetzner server and verify the deployment

## Alternatives Considered

1. **GitLab CI** - Would require migrating the repository
2. **Jenkins** - More complex setup, requires hosting Jenkins server
3. **Manual deployment** - Current approach, error-prone and slow

## Decision

Use GitHub Actions as described above. It's free for public repos, integrates directly with GitHub, and requires no additional infrastructure.
