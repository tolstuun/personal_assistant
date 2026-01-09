# Configuration

This directory contains all configuration files for Personal Assistant.

## Structure

```
config/
├── llm.yaml              # LLM providers and API keys (create from example)
├── llm.example.yaml      # Example LLM config (committed to git)
├── storage.yaml          # Database and storage settings
│
├── my_profile/           # Your personal data for Job Hunter
│   ├── story.yaml       # Your narrative, how you position yourself
│   ├── facts.yaml       # Concrete achievements with metrics
│   └── cv_template.md   # Base CV template
│
├── sources/              # Data sources for crawling
│   ├── security_news.yaml
│   ├── market_reports.yaml
│   └── vendors.yaml
│
└── agents/               # Per-agent settings
    ├── security_digest.yaml
    ├── job_hunter.yaml
    └── ...
```

## Environment Variables

Sensitive data (API keys, passwords) should be in environment variables, not YAML files.

The config loader supports `${VAR_NAME}` and `${VAR_NAME:-default}` syntax:

```yaml
api_key: ${ANTHROPIC_API_KEY}
password: ${DB_PASSWORD:-changeme}
```

Required environment variables:
- `ANTHROPIC_API_KEY` — For Claude models
- `OPENAI_API_KEY` — For GPT models (optional)
- `POSTGRES_PASSWORD` — Database password

## Quick Start

1. Copy example configs:
   ```bash
   cp config/llm.example.yaml config/llm.yaml
   ```

2. Set environment variables:
   ```bash
   export ANTHROPIC_API_KEY="sk-..."
   ```

3. Edit configs as needed

## Config Merging

Configs are loaded in order:
1. `*.example.yaml` — Defaults (committed to git)
2. `*.yaml` — Your overrides (gitignored)

Later files override earlier ones.
