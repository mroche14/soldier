# Quickstart: Production Store & Provider Completion

**Feature**: 009-production-stores-providers
**Date**: 2025-11-29

## Prerequisites

1. **Docker Desktop** running (for PostgreSQL + Redis containers)
2. **Python 3.11+** installed
3. **uv** package manager installed
4. API keys (optional, for provider integration tests):
   - `ANTHROPIC_API_KEY`
   - `OPENAI_API_KEY`

## Setup

### 1. Start Infrastructure

```bash
# Start PostgreSQL (with pgvector) and Redis
docker-compose up -d postgres redis

# Verify containers are running
docker-compose ps
```

### 2. Install Dependencies

```bash
# Install base + postgres + migrations dependencies
uv sync
uv add asyncpg pgvector alembic
```

### 3. Run Database Migrations

```bash
# Initialize database schema
cd focal/db
alembic upgrade head

# Check migration status
alembic current
```

### 4. Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit .env with your settings:
# DATABASE_URL=postgresql://focal:focal@localhost:5432/focal
# REDIS_URL=redis://localhost:6379/0
# ANTHROPIC_API_KEY=sk-ant-...  (optional)
# OPENAI_API_KEY=sk-...  (optional)
```

## Running Tests

### Integration Tests (requires Docker)

```bash
# Run all store integration tests
uv run pytest tests/integration/stores/ -v

# Run specific store tests
uv run pytest tests/integration/stores/test_postgres_config.py -v
uv run pytest tests/integration/stores/test_redis_session.py -v

# Run provider tests (requires API keys)
uv run pytest tests/integration/providers/ -v
```

### Skip Tests Without Infrastructure

Tests automatically skip when infrastructure is unavailable:

```bash
# If Docker not running, store tests skip
# If API keys not set, provider tests skip
uv run pytest tests/integration/ -v
# Shows: SKIPPED [1] tests/integration/stores/test_postgres_config.py: Docker not available
```

## Quick Validation

### Verify PostgreSQL Store

```python
import asyncio
from focal.alignment.stores.postgres import PostgresConfigStore

async def test_postgres():
    store = PostgresConfigStore("postgresql://focal:focal@localhost:5432/focal")
    await store.connect()

    # Test basic operation
    agents, count = await store.get_agents(tenant_id=some_uuid)
    print(f"Found {count} agents")

    await store.close()

asyncio.run(test_postgres())
```

### Verify Redis Store

```python
import asyncio
from focal.conversation.stores.redis import RedisSessionStore

async def test_redis():
    store = RedisSessionStore("redis://localhost:6379/0")
    await store.connect()

    # Test health check
    healthy = await store.health_check()
    print(f"Redis healthy: {healthy}")

    await store.close()

asyncio.run(test_redis())
```

### Verify Migrations

```bash
# Check current migration version
cd focal/db
alembic current

# Show migration history
alembic history

# Rollback one version (if needed)
alembic downgrade -1
```

## Common Issues

### PostgreSQL Connection Failed

```bash
# Check container is running
docker-compose ps postgres

# Check logs
docker-compose logs postgres

# Verify port is accessible
pg_isready -h localhost -p 5432
```

### Redis Connection Failed

```bash
# Check container is running
docker-compose ps redis

# Test connection
redis-cli -h localhost -p 6379 ping
# Should return: PONG
```

### pgvector Extension Not Found

```bash
# Connect to PostgreSQL and enable extension
docker-compose exec postgres psql -U focal -d focal -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Migration Conflicts

```bash
# If migrations are out of sync
cd focal/db
alembic stamp head  # Mark current as head
alembic upgrade head  # Reapply if needed
```

## Development Workflow

1. **Make schema changes**: Update data-model.md first
2. **Generate migration**: `alembic revision -m "description"`
3. **Edit migration**: Add upgrade/downgrade SQL
4. **Test locally**: `alembic upgrade head`
5. **Run integration tests**: `uv run pytest tests/integration/stores/ -v`
6. **Commit**: Include migration file in commit

## File Locations

| Component | Location |
|-----------|----------|
| PostgreSQL stores | `focal/*/stores/postgres.py` |
| Redis session store | `focal/conversation/stores/redis.py` |
| Alembic config | `focal/db/alembic.ini` |
| Migration scripts | `focal/db/migrations/versions/` |
| Integration tests | `tests/integration/stores/`, `tests/integration/providers/` |
| Docker Compose | `docker-compose.yml` |
