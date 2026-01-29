# Decision 006: Content Fetcher for Security Digest

**Date:** 2026-01-29
**Status:** Proposed
**Author:** Claude (AI Assistant)

## Problem

The Security Digest system has:
- Categories and Sources defined in the database (via Admin UI)
- Article model ready to store fetched content

Now we need the fetching logic:
1. Fetch content from source URLs (websites, Twitter, Reddit)
2. Extract article links from listing pages
3. Parse article content (title, text, date) from each article page
4. Store articles in the database with deduplication
5. Apply keyword filtering based on source and category keywords
6. Track when sources were last fetched to respect fetch intervals

## Solution

### Architecture

```
src/core/primitives/fetchers/
├── __init__.py           # Public exports
├── base.py               # Base fetcher interface
├── website.py            # Website/RSS fetcher using trafilatura
├── twitter.py            # Twitter/X fetcher (stub)
├── reddit.py             # Reddit fetcher (stub)
└── manager.py            # Orchestrates fetching from all sources

tests/core/primitives/fetchers/
├── __init__.py
├── test_website.py
└── test_manager.py
```

### Component Details

#### 1. Website Fetcher (`website.py`)

Uses the existing `Fetcher` primitive to download HTML, then:
1. Parses the listing page to find article links
2. For each article link:
   - Fetches the article page
   - Uses `trafilatura` to extract: title, main text, publication date
   - Returns structured article data

```python
@dataclass
class ExtractedArticle:
    url: str
    title: str
    content: str
    published_at: datetime | None
    source_url: str  # Original listing page

async def fetch_articles(source_url: str, max_articles: int = 20) -> list[ExtractedArticle]
```

**Why trafilatura?**
- Specialized for article extraction from news sites
- Handles readability, boilerplate removal automatically
- Extracts metadata (title, date, author)
- Actively maintained, well-tested on real websites

#### 2. Fetcher Manager (`manager.py`)

Orchestrates the fetching workflow:

```python
class FetcherManager:
    async def fetch_due_sources(self) -> FetchResult
    async def fetch_source(self, source_id: UUID) -> list[Article]
```

**Responsibilities:**
1. Query database for enabled sources where:
   - `last_fetched_at` is NULL, OR
   - `last_fetched_at + fetch_interval_minutes < now()`
2. For each source, dispatch to appropriate fetcher (website/twitter/reddit)
3. For each extracted article:
   - Check if URL already exists in database (deduplication)
   - Apply keyword filtering (source keywords + category keywords)
   - Store new articles with `source_id` set
4. Update `source.last_fetched_at` after fetch

#### 3. Keyword Filtering

An article passes the filter if:
- No keywords defined (source + category both empty) → passes
- Any keyword from source OR category appears in title or content → passes

```python
def matches_keywords(article: ExtractedArticle, source: Source) -> bool:
    keywords = set(source.keywords + source.category.keywords)
    if not keywords:
        return True
    text = (article.title + " " + article.content).lower()
    return any(kw.lower() in text for kw in keywords)
```

#### 4. Twitter and Reddit Stubs

Placeholder implementations that raise `NotImplementedError`:

```python
class TwitterFetcher:
    async def fetch_articles(self, source: Source) -> list[ExtractedArticle]:
        raise NotImplementedError("Twitter fetcher coming soon")
```

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          FetcherManager.fetch_due_sources()             │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  1. Query: SELECT * FROM sources WHERE enabled=true                      │
│            AND (last_fetched_at IS NULL                                  │
│                OR last_fetched_at + interval < now())                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  2. For each source, dispatch to fetcher by type:                        │
│     - website → WebsiteFetcher.fetch_articles(source.url)               │
│     - twitter → TwitterFetcher (stub)                                    │
│     - reddit  → RedditFetcher (stub)                                     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  3. WebsiteFetcher:                                                      │
│     a. Fetch listing page HTML                                           │
│     b. Extract article links (<a> tags in main content)                  │
│     c. For each link, fetch article page                                 │
│     d. Use trafilatura to extract title, content, date                   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  4. For each extracted article:                                          │
│     a. Check URL not in articles table (dedup)                           │
│     b. Check keyword match (source + category keywords)                  │
│     c. INSERT into articles table                                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  5. UPDATE source SET last_fetched_at = now()                            │
└─────────────────────────────────────────────────────────────────────────┘
```

### CLI Test Script

A simple script to test fetching from a single source:

```bash
python -m src.core.primitives.fetchers.test_fetch <source_id>
```

This will:
1. Load the source from database
2. Run the appropriate fetcher
3. Print extracted articles (without saving to database)
4. Useful for testing new sources before enabling them

### Dependencies

Add to `pyproject.toml`:
```toml
"trafilatura>=2.0.0"
```

trafilatura includes:
- HTML parsing (lxml)
- Readability algorithm
- Date extraction
- Metadata parsing

## How to Test

### Prerequisites
```bash
docker-compose up -d postgres
alembic upgrade head  # Ensure tables exist
```

### Run Unit Tests
```bash
pytest tests/core/primitives/fetchers/ -v
```

### Test CLI Manually
```bash
# First, create a source via Admin UI at http://localhost:8000/admin/

# Then test fetching (dry run, doesn't save to DB)
python -m src.core.primitives.fetchers.test_fetch <source-uuid>
```

### Test with Real URL
```python
# In Python REPL
from src.core.primitives.fetchers.website import WebsiteFetcher

fetcher = WebsiteFetcher()
articles = await fetcher.fetch_articles("https://krebsonsecurity.com/")
for a in articles[:5]:
    print(f"- {a.title}")
```

## Alternatives Considered

1. **newspaper3k** — Popular but less maintained, more dependencies
2. **BeautifulSoup only** — Manual parsing, would need custom rules per site
3. **Scrapy** — Full framework, overkill for our use case
4. **RSS only** — Many sites don't have RSS, limits sources

## Decision

Implement content fetcher as described using trafilatura for article extraction. This provides:
- Robust extraction from most news/blog sites
- Minimal custom parsing code
- Clean integration with existing primitives
- Easy to extend with Twitter/Reddit later
