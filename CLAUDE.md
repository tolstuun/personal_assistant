# Project: Personal Assistant

## Overview
Modular AI assistant with atomic components. Owner is non-technical - documentation, testing, and clear git history are critical.

## Tech Stack
- Python 3.11+
- FastAPI (REST API)
- LiteLLM (LLM abstraction)
- PostgreSQL (relational data)
- Redis (caching)
- Qdrant (vector search)
- Telegram Bot (user interface)
- Docker Compose (infrastructure)

## Code Standards
- Type hints on ALL functions
- Docstrings on ALL public functions (explain what it does in plain English)
- PEP 8 compliance (use ruff)
- One component = one responsibility (atomicity)
- Config in YAML, not hardcoded

## Workflow Rules (MUST FOLLOW)

### 1. Documentation First
Before writing any code:
- Create or update a decision doc in docs/decisions/NNN-feature-name.md
- Include: Problem, Solution, How to Test (commands a non-programmer can run)
- Update docs/changelog.md with plain English summary

### 2. Branch Strategy
- Never commit directly to master
- Create feature branch: git checkout -b feat/feature-name
- Do all work on the branch
- When complete, push branch and note that it's ready for review

### 3. Testing Requirements
- Write tests for ALL new code
- Tests go in tests/ mirroring src/ structure
- Run pytest before every commit
- If tests fail, fix before committing
- Aim for tests that verify the feature works end-to-end

### 4. Commit Strategy
- Commit after completing each logical component
- Use conventional commits:
  - feat(scope): add new feature
  - fix(scope): bug fix
  - docs(scope): documentation
  - test(scope): adding tests
- Write clear commit messages explaining WHAT and WHY

### 5. After Completing Any Task
- Update PROGRESS.md
- Update docs/changelog.md
- Ensure all tests pass
- Push to remote

## Commands

**Note:** Additional tools are installed in `~/.local/bin` (including `gh` CLI). Add to PATH if needed:
```bash
export PATH="$HOME/.local/bin:$PATH"
```

- Run app: python run.py
- Run tests: pytest
- Run single test file: pytest tests/path/to/test.py -v
- Lint: ruff check .
- Format: ruff format .
- Type check: mypy src/
- Start infrastructure: docker-compose up -d
- Stop infrastructure: docker-compose down
- GitHub CLI: ~/.local/bin/gh (or just `gh` if PATH is set)

## Project Structure
- src/core/ - foundational components (llm, config, primitives, storage)
- src/agents/ - individual agents (security_digest, job_hunter, etc.)
- src/orchestrator/ - task routing and coordination
- src/api/ - REST API endpoints
- interfaces/ - user interfaces (telegram bot)
- config/ - YAML configuration files
- tests/ - mirrors src/ structure
- docs/decisions/ - architecture decision records
- docs/guides/ - how-to guides for the owner
- docs/changelog.md - plain English change history

## Secrets Management

**IMPORTANT:** Never commit secrets (API keys, tokens, passwords) to git.

### How It Works
1. **Config files with secrets live ONLY on the Hetzner server**, never in git:
   - `config/telegram.yaml` - Telegram bot token
   - `config/llm.yaml` - LLM API keys (OpenAI, Anthropic, etc.)
   - `config/storage.yaml` - Database passwords, Redis passwords, etc.

2. **Git contains only `*.example.yaml` templates** that show the structure without real values

3. **These files are in `.gitignore`** so they can't be accidentally committed

### Adding New Config That Needs Secrets
1. Create `config/new-feature.example.yaml` with placeholder values or `${ENV_VAR}` syntax
2. Add `config/new-feature.yaml` to `.gitignore`
3. On the server, copy the example and fill in real values

### How Deployment Works
- Deploy script (`~/personal_assistant/deploy.sh`) pulls code from git
- Config files on the server stay untouched (they're not in git)
- This means secrets persist across deployments

### Setting Up a New Server
1. Clone the repository
2. Copy each example config to its real name:
   ```bash
   cp config/telegram.example.yaml config/telegram.yaml
   cp config/llm.example.yaml config/llm.yaml
   cp config/storage.example.yaml config/storage.yaml
   ```
3. Edit each file and fill in real values
4. Set environment variables for sensitive values:
   ```bash
   export TELEGRAM_BOT_TOKEN="your-token-here"
   export ANTHROPIC_API_KEY="sk-ant-..."
   ```

## For the Non-Technical Owner
After any work session, you can:
1. Run `pytest` to verify everything works
2. Check docs/changelog.md to see what changed
3. Read docs/decisions/ to understand why choices were made
4. Check PROGRESS.md for overall project status
