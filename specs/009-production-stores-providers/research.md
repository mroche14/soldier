# Research: Production Store & Provider Completion

**Feature**: 009-production-stores-providers
**Date**: 2025-11-29

## Research Topics

### 1. Redis Two-Tier Session Storage Pattern

**Decision**: Implement two-tier storage using Redis key prefixes with separate TTLs

**Rationale**:
- Hot tier (`session:hot:{id}`) uses Redis string with short TTL (30 min default)
- Persistent tier (`session:persist:{id}`) uses Redis hash with long TTL (7 days default)
- On access, check hot tier first, then persistent; promote to hot if found in persistent
- On TTL expiry in hot tier, Redis keyspace notifications trigger demotion to persistent
- Use Redis MULTI/EXEC for atomic tier transitions

**Alternatives Considered**:
1. **Single tier with TTL refresh**: Rejected - all sessions would need same TTL, wastes memory
2. **Redis Streams**: Rejected - overkill for key-value session data, adds complexity
3. **External timer for demotion**: Rejected - Redis native TTL + notifications more reliable

**Implementation Pattern**:
```python
# Key structure
HOT_KEY = "session:hot:{session_id}"      # TTL: 30min, String (JSON)
PERSIST_KEY = "session:persist:{session_id}"  # TTL: 7days, String (JSON)

# Read: check hot first, fallback to persistent, promote if needed
# Write: always to hot tier
# TTL expiry: keyspace notification triggers copy to persistent before delete
```

### 2. Alembic Migration Best Practices for Multi-Store Schema

**Decision**: Single Alembic configuration with modular migration scripts per store domain

**Rationale**:
- One `alembic.ini` at `soldier/db/alembic.ini`
- Migration versions in `soldier/db/migrations/versions/`
- Each migration file prefixed by domain: `001_config_store_`, `002_memory_store_`, etc.
- Use `op.create_table()` with explicit schema names for clarity
- Include both upgrade and downgrade paths for all migrations

**Alternatives Considered**:
1. **Separate Alembic configs per store**: Rejected - complicates deployment, version tracking
2. **Raw SQL files**: Rejected - loses Alembic's version tracking and rollback benefits
3. **SQLAlchemy ORM models**: Rejected - project uses raw asyncpg, ORM would add complexity

**Migration Naming Convention**:
```
versions/
├── 001_initial_config_store.py
├── 002_initial_memory_store.py
├── 003_initial_audit_store.py
├── 004_initial_profile_store.py
└── 005_add_pgvector_indexes.py
```

### 3. PostgreSQL with pgvector for Vector Search

**Decision**: Use pgvector extension with IVFFlat index for approximate nearest neighbor search

**Rationale**:
- pgvector integrates natively with PostgreSQL - no separate vector DB needed
- IVFFlat index provides good balance of speed vs accuracy for 10k-100k vectors
- Use `vector(1536)` dimension for OpenAI embeddings compatibility
- Cosine similarity via `<=>` operator matches existing in-memory implementation

**Alternatives Considered**:
1. **HNSW index**: Better for larger datasets but more memory-intensive; IVFFlat sufficient for current scale
2. **Exact search without index**: Too slow for production (O(n) scan)
3. **Separate vector DB (Pinecone, Weaviate)**: Rejected - adds operational complexity, pgvector sufficient

**Index Configuration**:
```sql
-- Create vector column
ALTER TABLE episodes ADD COLUMN embedding vector(1536);

-- Create IVFFlat index (lists = sqrt(n) is good default, n=10000 -> lists=100)
CREATE INDEX idx_episodes_embedding ON episodes
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

### 4. asyncpg Connection Pool Best Practices

**Decision**: Use asyncpg pool with sensible defaults, health checks, and graceful shutdown

**Rationale**:
- asyncpg is the fastest PostgreSQL driver for Python async
- Connection pool manages connection lifecycle
- Health checks detect stale connections
- Graceful shutdown prevents connection leaks

**Pool Configuration**:
```python
pool = await asyncpg.create_pool(
    dsn=database_url,
    min_size=5,          # Minimum connections to keep open
    max_size=20,         # Maximum connections
    max_inactive_connection_lifetime=300,  # 5 min idle timeout
    command_timeout=60,  # Query timeout
)
```

### 5. Integration Test Infrastructure with Docker

**Decision**: pytest fixtures with docker-compose for PostgreSQL + pgvector and Redis

**Rationale**:
- `pytest-docker` or manual subprocess control for container lifecycle
- Use unique database names per test session to avoid conflicts
- Skip tests gracefully if Docker not available
- Clean up containers after test session

**Alternatives Considered**:
1. **Testcontainers-python**: Good option but adds dependency; manual approach simpler
2. **Shared test database**: Rejected - test isolation issues
3. **Mock databases**: Rejected - defeats purpose of integration tests

**Test Fixture Pattern**:
```python
@pytest.fixture(scope="session")
async def postgres_pool():
    """Create PostgreSQL connection pool for tests."""
    if not docker_available():
        pytest.skip("Docker not available")

    # Start container, create pool, yield, cleanup
    ...

@pytest.fixture(scope="session")
async def redis_client():
    """Create Redis client for tests."""
    if not docker_available():
        pytest.skip("Docker not available")
    ...
```

### 6. Provider Integration Test Pattern

**Decision**: Use pytest markers and environment variable checks for API key availability

**Rationale**:
- Tests skip cleanly when API keys not configured
- Use `@pytest.mark.integration` marker for filtering
- Mock responses for rate limit handling
- Keep test data minimal to reduce API costs

**Implementation Pattern**:
```python
@pytest.fixture
def anthropic_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    return key

@pytest.mark.integration
async def test_anthropic_generate(anthropic_api_key):
    provider = AnthropicProvider(api_key=anthropic_api_key)
    response = await provider.generate("Say hello")
    assert response.content
```

### 7. Redis Connection Handling and Error Recovery

**Decision**: Use redis-py async client with connection pool and explicit error handling

**Rationale**:
- redis-py 7.x has mature async support
- Connection pool handles reconnection automatically
- Wrap operations in try/except for graceful degradation
- Use health checks before critical operations

**Error Handling Pattern**:
```python
class RedisSessionStore(SessionStore):
    async def get(self, session_id: UUID) -> Session | None:
        try:
            data = await self._client.get(self._hot_key(session_id))
            if data:
                return Session.model_validate_json(data)
            # Check persistent tier...
        except RedisError as e:
            logger.error("redis_error", error=str(e), operation="get")
            raise StoreError(f"Redis unavailable: {e}") from e
```

## Dependencies to Add

```toml
[project.optional-dependencies]
postgres = [
    "asyncpg>=0.29",
    "pgvector>=0.3",
]
migrations = [
    "alembic>=1.13",
    "asyncpg>=0.29",
]
```

## Docker Compose Updates

Update `docker-compose.yml` to use pgvector image:

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16  # Changed from postgres:16-alpine
    # ... rest unchanged
```

## Summary

All technical decisions align with:
- Existing async-first architecture
- Store ABC interface patterns
- Multi-tenant design requirements
- Performance targets from spec

No blocking issues or unknowns remaining.
