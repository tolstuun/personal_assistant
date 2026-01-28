# Decision 001: Storage Layer Design

**Date:** 2026-01-28
**Status:** Proposed
**Author:** Claude (AI Assistant)

## Problem

The Personal Assistant needs persistent storage for:
- **Structured data** — User profiles, agent states, task history, conversation logs
- **Caching** — Frequently accessed data, rate limiting, session state
- **Vector search** — RAG (retrieval-augmented generation) for knowledge base queries
- **File storage** — Documents, images, exported reports

Currently, `src/core/storage/` is empty. We need to implement storage abstractions that:
1. Follow existing code patterns (abstract base + concrete implementation + factory)
2. Work with the infrastructure already defined in `docker-compose.yaml`
3. Are easy to test and mock
4. Support async operations throughout

## Solution

### Storage Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| `postgres.py` | PostgreSQL + SQLAlchemy | Relational data, transactions |
| `redis_cache.py` | Redis | Caching, pub/sub, task queues |
| `vector_store.py` | Qdrant | Semantic search, embeddings |
| `file_storage.py` | MinIO (S3-compatible) | Binary files, documents |

### Design Pattern

Follow the established pattern from `src/core/llm/`:

```
src/core/storage/
├── __init__.py          # Public API exports
├── base.py              # Abstract base classes
├── postgres.py          # PostgreSQL implementation
├── redis_cache.py       # Redis implementation
├── vector_store.py      # Qdrant implementation
├── file_storage.py      # MinIO/S3 implementation
└── models.py            # SQLAlchemy models (tables)
```

### Configuration

Add `config/storage.example.yaml`:

```yaml
postgres:
  host: ${POSTGRES_HOST:-localhost}
  port: ${POSTGRES_PORT:-5432}
  database: ${POSTGRES_DB:-assistant}
  user: ${POSTGRES_USER:-assistant}
  password: ${POSTGRES_PASSWORD:-assistant}
  pool_size: 5
  echo: false  # SQL logging

redis:
  host: ${REDIS_HOST:-localhost}
  port: ${REDIS_PORT:-6379}
  db: 0
  password: ${REDIS_PASSWORD:-}
  default_ttl: 3600  # 1 hour

qdrant:
  host: ${QDRANT_HOST:-localhost}
  port: ${QDRANT_PORT:-6333}
  grpc_port: ${QDRANT_GRPC_PORT:-6334}
  collection_prefix: assistant_

minio:
  endpoint: ${MINIO_ENDPOINT:-localhost:9000}
  access_key: ${MINIO_ACCESS_KEY:-minioadmin}
  secret_key: ${MINIO_SECRET_KEY:-minioadmin}
  bucket: ${MINIO_BUCKET:-assistant}
  secure: false  # Use HTTPS
```

### API Design

#### PostgreSQL (postgres.py)

```python
from src.core.storage import get_db, Database

# Get database instance
db = await get_db()

# Use session context manager
async with db.session() as session:
    result = await session.execute(query)

# Health check
is_healthy = await db.health_check()
```

#### Redis Cache (redis_cache.py)

```python
from src.core.storage import get_cache, Cache

cache = await get_cache()

# Basic operations
await cache.set("key", value, ttl=3600)
value = await cache.get("key")
await cache.delete("key")

# JSON operations (auto serialize/deserialize)
await cache.set_json("user:123", {"name": "John"})
user = await cache.get_json("user:123")
```

#### Vector Store (vector_store.py)

```python
from src.core.storage import get_vector_store, VectorStore

store = await get_vector_store()

# Add documents with embeddings
await store.upsert(
    collection="knowledge",
    documents=[
        {"id": "doc1", "text": "...", "embedding": [...], "metadata": {...}}
    ]
)

# Search by vector
results = await store.search(
    collection="knowledge",
    embedding=[...],
    limit=10
)
```

#### File Storage (file_storage.py)

```python
from src.core.storage import get_file_storage, FileStorage

storage = await get_file_storage()

# Upload/download
url = await storage.upload("reports/2024/jan.pdf", file_bytes)
content = await storage.download("reports/2024/jan.pdf")

# Presigned URLs for direct access
url = await storage.get_presigned_url("reports/2024/jan.pdf", expires=3600)
```

### Implementation Priority

1. **PostgreSQL** — Most critical, needed for user data and agent state
2. **Redis** — Needed for caching LLM responses and session management
3. **Vector Store** — Needed for RAG in agents
4. **File Storage** — Lower priority, can be added later

### Error Handling

Each storage component raises specific exceptions:

```python
from src.core.storage.exceptions import (
    StorageError,           # Base exception
    ConnectionError,        # Can't connect to service
    NotFoundError,          # Item doesn't exist
    DuplicateError,         # Unique constraint violation
)
```

## How to Test

### Prerequisites
Start the infrastructure:
```bash
docker-compose up -d postgres redis qdrant minio
```

### Run All Storage Tests
```bash
pytest tests/core/storage/ -v
```

### Test Individual Components
```bash
# PostgreSQL
pytest tests/core/storage/test_postgres.py -v

# Redis
pytest tests/core/storage/test_redis_cache.py -v

# Vector store
pytest tests/core/storage/test_vector_store.py -v

# File storage
pytest tests/core/storage/test_file_storage.py -v
```

### Verify Services Are Running
```bash
# PostgreSQL
docker-compose exec postgres pg_isready

# Redis
docker-compose exec redis redis-cli ping

# Qdrant
curl http://localhost:6333/health

# MinIO
curl http://localhost:9000/minio/health/live
```

## Alternatives Considered

1. **SQLite instead of PostgreSQL** — Simpler but doesn't scale, no async support
2. **Memcached instead of Redis** — No pub/sub, no persistence
3. **Pinecone instead of Qdrant** — Cloud-only, costs money, Qdrant is self-hosted
4. **Local filesystem instead of MinIO** — Not S3-compatible, harder to migrate

## Decision

Implement all four storage components following the design above. Start with PostgreSQL and Redis, then add Qdrant and MinIO.
