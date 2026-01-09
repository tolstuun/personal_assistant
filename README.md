# Personal Assistant

A modular AI assistant with atomic components.

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/avoitenko16/personal_assistant.git
cd personal_assistant

# 2. Copy config
cp config/llm.example.yaml config/llm.yaml
# Add your API keys to config/llm.yaml

# 3. Start infrastructure
docker-compose up -d

# 4. Install dependencies
pip install -e .

# 5. Verify everything works
python -m src.core.llm.test_connection
```

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — Full architecture description
- [PROGRESS.md](PROGRESS.md) — What's done, what's planned
- [config/README.md](config/README.md) — Configuration guide

## Agents

| Agent | Status | Description |
|-------|--------|-------------|
| Security Digest | 🔲 planned | Cybersecurity news digest |
| Job Hunter | 🔲 planned | CV adaptation, job applications |
| Calendar Sync | 🔲 planned | Google + O365 synchronization |
| Code Assistant | 🔲 planned | Coding help, API knowledge |
| Market Intel | 🔲 planned | Analytics, Gartner reports, etc. |
| Red Team Tools | 🔲 planned | Security training tools |

## Principles

1. **Atomicity** — Each component does one thing
2. **Interchangeability** — LLM providers can be swapped with one line
3. **Configuration separated from code** — Everything in YAML
4. **Verification** — Fighting hallucinations at every step
5. **Modularity** — Agents are independent of each other

## License

Private / Personal Use
