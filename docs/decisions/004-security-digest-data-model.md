# Decision 004: Security Digest Data Model

**Date:** 2026-01-28
**Status:** Proposed
**Author:** Claude (AI Assistant)

## Problem

The Personal Assistant needs a Security Digest system that:
- Monitors multiple sources (websites, Twitter, Reddit) for security-related content
- Categorizes content into sections (security news, product news, market trends)
- Generates periodic digest reports with summaries
- Tracks what has been published and when

We need a data model that supports:
1. Flexible source configuration with keywords and fetch intervals
2. Article storage with AI-generated summaries and relevance scores
3. Digest generation workflow (building → ready → published)
4. Category-based organization for the final digest sections

## Solution

### Data Model Overview

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  categories │────<│   sources   │────<│  articles   │>────│   digests   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

### Tables

#### 1. categories
Defines content categories that map to digest sections.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| name | VARCHAR(100) | Category name (e.g., "CVE Alerts", "Cloud Security") |
| digest_section | VARCHAR(50) | Section in digest: security_news, product_news, market |
| keywords | TEXT[] | Array of keywords for relevance matching |
| created_at | TIMESTAMP | When category was created |

#### 2. sources
Defines where to fetch content from.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| category_id | UUID | Foreign key to categories |
| name | VARCHAR(200) | Human-readable name |
| url | TEXT | Source URL or API endpoint |
| source_type | VARCHAR(20) | website, twitter, reddit |
| keywords | TEXT[] | Source-specific filter keywords |
| enabled | BOOLEAN | Whether to fetch from this source |
| fetch_interval_minutes | INTEGER | How often to check (default: 60) |
| last_fetched_at | TIMESTAMP | Last successful fetch time |
| created_at | TIMESTAMP | When source was added |

#### 3. articles
Stores fetched content and AI-generated analysis.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| source_id | UUID | Foreign key to sources |
| url | TEXT | Original article URL (unique) |
| title | VARCHAR(500) | Article title |
| raw_content | TEXT | Full content (for re-processing) |
| summary | TEXT | AI-generated summary |
| digest_section | VARCHAR(50) | Assigned section for digest |
| relevance_score | FLOAT | 0.0-1.0 relevance rating |
| fetched_at | TIMESTAMP | When article was fetched |
| digest_id | UUID | Foreign key to digests (nullable) |

#### 4. digests
Tracks digest generation and publishing.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| date | DATE | Digest date (unique) |
| status | VARCHAR(20) | building, ready, published |
| html_path | TEXT | Path to generated HTML file |
| created_at | TIMESTAMP | When digest build started |
| published_at | TIMESTAMP | When digest was published |
| notified_at | TIMESTAMP | When notification was sent |

### Relationships

- **categories → sources**: One-to-many. Each source belongs to one category.
- **sources → articles**: One-to-many. Each article comes from one source.
- **digests → articles**: One-to-many. Articles are assigned to a digest when included.

### Workflow

1. **Fetch**: Scheduler runs fetchers based on `fetch_interval_minutes`
2. **Process**: LLM generates summaries and assigns `relevance_score`
3. **Build Digest**: Create digest record (status=building), assign high-relevance articles
4. **Generate**: Create HTML from assigned articles, update `html_path`
5. **Publish**: Update status=published, send notification, set timestamps

### Indexes

For query performance:
- `articles.url` — UNIQUE for deduplication
- `articles.fetched_at` — Filter recent articles
- `articles.relevance_score` — Sort by relevance
- `articles.digest_id` — Find articles in a digest
- `sources.enabled` — Filter active sources
- `sources.last_fetched_at` — Find sources due for fetch
- `digests.date` — UNIQUE, lookup by date
- `digests.status` — Filter by workflow state

### File Structure

```
src/core/models/
├── __init__.py           # Public exports
├── base.py               # Base model with common fields
└── security_digest.py    # Category, Source, Article, Digest models

alembic/
├── alembic.ini           # Alembic configuration
├── env.py                # Migration environment
└── versions/             # Migration files
    └── 001_create_security_digest_tables.py
```

## How to Test

### Prerequisites
```bash
docker-compose up -d postgres
```

### Run Model Tests
```bash
pytest tests/core/models/test_security_digest.py -v
```

### Verify Tables Exist
```bash
# After running migrations
docker-compose exec postgres psql -U assistant -d assistant -c "\dt"
```

### Test Migration
```bash
# Apply migrations
alembic upgrade head

# Check current version
alembic current

# Rollback
alembic downgrade -1
```

## Alternatives Considered

1. **Single table for all content** — Simpler but harder to query, no source tracking
2. **NoSQL (MongoDB)** — More flexible but loses relational integrity
3. **Separate databases per agent** — Overkill, adds operational complexity

## Decision

Implement the four-table model as described. Use SQLAlchemy models with Alembic for migrations. This provides:
- Clear separation of concerns
- Flexible source management
- Full audit trail of fetched content
- Workflow state tracking for digests
