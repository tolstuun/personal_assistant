# 012: Digest Generator

## Status
Accepted

## Problem
We have articles fetched from sources and stored in the database, but no way to turn them into a readable daily digest. We need a service that:
- Collects unprocessed articles (those not yet assigned to a digest)
- Summarizes them using the configured LLM
- Groups them by section (security_news, product_news, market)
- Generates a clean HTML page
- Creates a Digest record to track the output

## Solution

### DigestService (`src/core/services/digest.py`)
A service class that orchestrates digest generation:

1. **Query** articles where `digest_id IS NULL`
2. **Filter** by enabled `digest_sections` setting
3. **Summarize** articles missing summaries using `SummarizerService`
4. **Group** articles by `digest_section`
5. **Render** HTML from a Jinja2 template
6. **Save** HTML to `data/digests/digest-YYYY-MM-DD.html`
7. **Create** a `Digest` record with `status=READY`
8. **Link** articles to the digest via `digest_id`

### HTML Output
- Standalone HTML page (no external dependencies)
- Mobile-friendly, clean layout
- Sections with article titles (linked to original URLs) and summaries
- Saved to `data/digests/` and served at `/digests/`

### Admin Integration
- "Generate Digest Now" button on the dashboard
- Manual trigger for testing before automating

### CLI
- `python -m src.core.services.digest --generate`

## Design Decisions
- **Local file storage** instead of MinIO — simpler, no extra infra
- **Summarize on demand** — only summarizes articles that don't have summaries yet
- **Standalone HTML** — no CDN dependencies, works as a shareable file
- **Reuses existing models** — Digest and Article models already have the right fields

## How to Test

```bash
# Run unit tests
pytest tests/core/services/test_digest.py -v

# Generate a digest manually (requires running database with articles)
python -m src.core.services.digest --generate

# Via admin UI: click "Generate Digest Now" on the dashboard
```
