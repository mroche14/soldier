# Implementation Plan: Production Store & Provider Completion

**Branch**: `009-production-stores-providers` | **Date**: 2025-11-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/009-production-stores-providers/spec.md`

## Summary

Complete the production-ready store and provider implementations for Focal by:
1. Implementing Redis two-tier session store with TTL management
2. Setting up Alembic database migrations for PostgreSQL schemas
3. Adding comprehensive integration tests for all production stores (PostgreSQL, Redis) and AI providers (Anthropic, OpenAI)

This completes Phases 16-17 of the implementation plan, making the system ready for production deployment.

## Technical Context

**Language/Version**: Python 3.11+ (using features like `tomllib`, `|` type unions)
**Primary Dependencies**:
- FastAPI 0.115+, Pydantic 2.0+, structlog 24.0+
- redis 7.1+ (async client for session store)
- asyncpg (PostgreSQL async driver)
- pgvector (PostgreSQL vector similarity extension)
- alembic (database migrations)
- pytest 8.0+, pytest-asyncio 0.23+

**Storage**:
- PostgreSQL 16+ with pgvector extension (ConfigStore, MemoryStore, AuditStore, ProfileStore)
- Redis 7+ (SessionStore with two-tier caching)

**Testing**: pytest with pytest-asyncio, Docker Compose for integration test infrastructure
**Target Platform**: Linux server (Docker containers)
**Project Type**: Single Python package with FastAPI backend
**Performance Goals**:
- 1000 concurrent session operations without errors
- 50ms per tier promotion/demotion
- 100ms vector search for 10k items
**Constraints**:
- All stores must implement existing ABC interfaces
- Must maintain backward compatibility with in-memory implementations
- Integration tests must skip gracefully when infrastructure unavailable
**Scale/Scope**:
- 4 PostgreSQL stores (ConfigStore, MemoryStore, AuditStore, ProfileStore)
- 1 Redis store (SessionStore)
- 2 provider integration test suites (Anthropic, OpenAI)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

No constitution file found - proceeding with standard patterns from existing codebase:
- Store implementations follow ABC interfaces defined in `store.py` files
- Async-first approach for all I/O operations
- Dependency injection for testability
- Multi-tenant scoping on all queries (tenant_id filtering)
- Structured logging with structlog

## Project Structure

### Documentation (this feature)

```text
specs/009-production-stores-providers/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
focal/
├── alignment/
│   └── stores/
│       ├── config_store.py     # ABC interface (exists)
│       ├── inmemory.py         # Reference implementation (exists)
│       └── postgres.py         # NEW: PostgresConfigStore
├── memory/
│   └── stores/
│       ├── store.py            # ABC interface (exists)
│       ├── inmemory.py         # Reference implementation (exists)
│       └── postgres.py         # STUB: PostgresMemoryStore with pgvector (needs implementation)
├── conversation/
│   └── stores/
│       ├── store.py            # ABC interface (exists)
│       ├── inmemory.py         # Reference implementation (exists)
│       └── redis.py            # ENHANCE: Two-tier RedisSessionStore
├── audit/
│   └── stores/
│       ├── store.py            # ABC interface (exists)
│       ├── inmemory.py         # Reference implementation (exists)
│       └── postgres.py         # STUB: PostgresAuditStore (needs implementation)
├── profile/
│   └── stores/
│       ├── store.py            # ABC interface (exists)
│       ├── inmemory.py         # Reference implementation (exists)
│       └── postgres.py         # NEW: PostgresProfileStore
├── providers/
│   ├── llm/
│   │   ├── anthropic.py        # EXISTS: Integration tests needed
│   │   └── openai.py           # EXISTS: Integration tests needed
│   └── embedding/
│       └── openai.py           # EXISTS: Integration tests needed
└── db/
    └── migrations/             # NEW: Alembic migrations
        ├── env.py
        ├── versions/
        └── alembic.ini

tests/
├── integration/
│   ├── stores/
│   │   ├── conftest.py         # NEW: Docker fixtures
│   │   ├── test_postgres_config.py
│   │   ├── test_postgres_memory.py
│   │   ├── test_postgres_audit.py
│   │   ├── test_postgres_profile.py
│   │   └── test_redis_session.py
│   └── providers/
│       ├── conftest.py         # NEW: API key fixtures
│       ├── test_anthropic.py
│       └── test_openai.py
└── contract/                   # Existing contract tests
```

**Structure Decision**: Follows existing project structure. New files integrate into existing directory hierarchy. Alembic migrations placed in new `focal/db/migrations/` directory.

## Complexity Tracking

No constitution violations - all patterns align with existing codebase architecture.
