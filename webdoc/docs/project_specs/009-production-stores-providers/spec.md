# Feature Specification: Production Store & Provider Completion

**Feature Branch**: `009-production-stores-providers`
**Created**: 2025-11-29
**Status**: Draft
**Input**: Complete Production Store & Provider implementations (Phases 16-17): Redis two-tier session caching with TTL management, Alembic database migrations for PostgreSQL schemas, and comprehensive integration tests for all production stores (PostgreSQL, Redis) and AI providers (Anthropic, OpenAI)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Redis Session Store with Two-Tier Caching (Priority: P1)

As a platform operator, I need session data to be reliably stored in Redis with a two-tier architecture (hot cache for active sessions + persistent tier for inactive sessions) so that the system can handle high concurrency while efficiently managing memory.

**Why this priority**: Sessions are the most frequently accessed data in production. Without a proper Redis implementation with TTL management, the in-memory store cannot scale beyond a single process and loses all data on restart.

**Independent Test**: Can be tested by running multiple concurrent session operations against a real Redis instance and verifying data persistence, TTL expiration, and tier promotion/demotion.

**Acceptance Scenarios**:

1. **Given** a new session is created, **When** the session is saved, **Then** it is stored in the hot cache tier with a configurable TTL
2. **Given** a session has been inactive beyond the hot cache TTL, **When** the TTL expires, **Then** the session is demoted to persistent storage (not deleted)
3. **Given** an inactive session in persistent storage, **When** the session is accessed, **Then** it is promoted back to the hot cache tier
4. **Given** Redis is temporarily unavailable, **When** a session operation fails, **Then** appropriate errors are raised without data corruption
5. **Given** a session exceeds the maximum age limit, **When** the cleanup runs, **Then** the session is permanently removed from all tiers

---

### User Story 2 - Alembic Database Migration System (Priority: P1)

As a platform operator, I need a database migration system so that I can safely evolve the PostgreSQL schema as the application grows, with version tracking and rollback capability.

**Why this priority**: Without schema migrations, deploying database changes to production is manual, error-prone, and not reproducible. This is a prerequisite for reliable production deployments.

**Independent Test**: Can be tested by running migration scripts against an empty database and verifying all tables/indexes are created correctly, then running a downgrade to verify rollback works.

**Acceptance Scenarios**:

1. **Given** a fresh PostgreSQL database, **When** migrations are run, **Then** all required tables, indexes, and constraints are created
2. **Given** an existing database with data, **When** a new migration is applied, **Then** existing data is preserved and new schema changes are applied
3. **Given** a migration has been applied, **When** a rollback is requested, **Then** the schema reverts to the previous state
4. **Given** migrations are run, **When** checking migration status, **Then** the current version and pending migrations are displayed

---

### User Story 3 - PostgreSQL Store Integration Tests (Priority: P2)

As a developer, I need comprehensive integration tests for all PostgreSQL stores so that I can verify the production implementations work correctly with real database operations.

**Why this priority**: Integration tests validate that the store implementations work with real PostgreSQL (including pgvector for similarity search). Without these tests, bugs will only be discovered in production.

**Independent Test**: Can be tested by running the integration test suite against a Docker PostgreSQL instance with pgvector extension.

**Acceptance Scenarios**:

1. **Given** a PostgreSQL database with pgvector, **When** ConfigStore tests run, **Then** all CRUD operations and vector search work correctly
2. **Given** a PostgreSQL database with pgvector, **When** MemoryStore tests run, **Then** episode storage and vector similarity search work correctly
3. **Given** a PostgreSQL database, **When** AuditStore tests run, **Then** turn records and events are correctly persisted and queried
4. **Given** a PostgreSQL database, **When** ProfileStore tests run, **Then** customer profiles and field updates work correctly

---

### User Story 4 - Redis Session Store Integration Tests (Priority: P2)

As a developer, I need integration tests for the Redis session store so that I can verify the two-tier caching, TTL management, and all session operations work correctly.

**Why this priority**: The Redis session store has complex two-tier logic that must be tested against a real Redis instance to ensure correct behavior.

**Independent Test**: Can be tested by running the integration test suite against a Docker Redis instance.

**Acceptance Scenarios**:

1. **Given** a Redis instance, **When** session CRUD tests run, **Then** all operations complete successfully
2. **Given** a Redis instance with TTL configuration, **When** TTL tests run, **Then** sessions expire and promote/demote correctly between tiers
3. **Given** a Redis instance, **When** concurrent session tests run, **Then** no race conditions or data corruption occurs

---

### User Story 5 - AI Provider Integration Tests (Priority: P3)

As a developer, I need integration tests for AI providers (Anthropic, OpenAI) so that I can verify the provider implementations work correctly with real API calls.

**Why this priority**: Provider implementations are already complete but untested against real APIs. These tests validate correctness and serve as regression tests for future changes.

**Independent Test**: Can be tested by running provider tests with valid API keys (skipped in CI if keys not present).

**Acceptance Scenarios**:

1. **Given** valid Anthropic API credentials, **When** LLM provider tests run, **Then** text generation and structured output work correctly
2. **Given** valid OpenAI API credentials, **When** LLM provider tests run, **Then** text generation and structured output work correctly
3. **Given** valid OpenAI API credentials, **When** embedding provider tests run, **Then** embeddings are generated with correct dimensions
4. **Given** missing API credentials, **When** provider tests run, **Then** tests are skipped gracefully with informative message

---

### Edge Cases

- What happens when Redis connection is lost mid-operation? (Should raise connection error, not corrupt data)
- How does the system handle concurrent writes to the same session? (Last-write-wins with optimistic locking)
- What happens when PostgreSQL vector search returns no results? (Return empty list, not error)
- How are database migrations handled when multiple instances start simultaneously? (Alembic handles locking)
- What happens when AI provider rate limits are hit during tests? (Retry with backoff, eventually fail gracefully)

## Requirements *(mandatory)*

### Functional Requirements

**Redis Session Store**:
- **FR-001**: System MUST implement RedisSessionStore with all SessionStore interface methods
- **FR-002**: System MUST support two-tier session storage (hot cache + persistent)
- **FR-003**: System MUST automatically demote inactive sessions from hot cache to persistent tier based on configurable TTL
- **FR-004**: System MUST automatically promote accessed sessions from persistent tier to hot cache
- **FR-005**: System MUST support configurable TTL for hot cache tier (default: 30 minutes)
- **FR-006**: System MUST support configurable maximum session age for permanent expiration (default: 7 days)
- **FR-007**: System MUST handle Redis connection failures gracefully without data corruption

**Database Migrations**:
- **FR-008**: System MUST use Alembic for PostgreSQL schema management
- **FR-009**: System MUST provide migration scripts for all PostgreSQL store tables
- **FR-010**: System MUST support forward migrations (upgrade)
- **FR-011**: System MUST support backward migrations (downgrade)
- **FR-012**: Migration scripts MUST be idempotent (safe to run multiple times)
- **FR-013**: System MUST track migration version in the database

**Integration Tests**:
- **FR-014**: System MUST provide integration tests for PostgresConfigStore (CRUD + vector search)
- **FR-015**: System MUST provide integration tests for PostgresMemoryStore (episodes + vector search)
- **FR-016**: System MUST provide integration tests for PostgresAuditStore (turns + events)
- **FR-017**: System MUST provide integration tests for PostgresProfileStore (profiles + fields)
- **FR-018**: System MUST provide integration tests for RedisSessionStore (CRUD + TTL + tiers)
- **FR-019**: System MUST provide integration tests for AnthropicProvider (generation + structured output)
- **FR-020**: System MUST provide integration tests for OpenAIProvider (generation + embeddings)
- **FR-021**: Provider integration tests MUST skip gracefully when API keys are not available
- **FR-022**: All integration tests MUST be runnable via Docker Compose for local development

### Key Entities

- **Session**: Active conversation state with tenant/agent/customer scoping, TTL metadata
- **MigrationVersion**: Alembic version tracking for schema state
- **ConfigStore Tables**: agents, rules, scenarios, templates, variables, tool_activations, migration_plans
- **MemoryStore Tables**: episodes (with pgvector embedding column), entities, relationships
- **AuditStore Tables**: turn_records, audit_events
- **ProfileStore Tables**: customer_profiles, channel_identities, profile_fields, profile_assets

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Redis session store handles 1000 concurrent session operations without errors
- **SC-002**: Session promotion/demotion between tiers completes in under 50ms per operation
- **SC-003**: Database migrations can be applied to an empty database in under 30 seconds
- **SC-004**: All integration tests pass with 100% success rate when infrastructure is available
- **SC-005**: Integration test suite completes in under 5 minutes for all stores and providers
- **SC-006**: Provider integration tests skip cleanly (no failures) when API keys are not configured
- **SC-007**: PostgreSQL vector search returns results in under 100ms for 10,000 stored items

## Assumptions

- PostgreSQL 14+ with pgvector extension is available for production deployments
- Redis 6+ is available for session storage in production
- Docker Desktop is running and available for local development and testing
- Docker Compose can spin up PostgreSQL (with pgvector) and Redis containers for integration tests
- API keys for Anthropic and OpenAI are available for provider integration tests (or tests skip gracefully)
- The existing in-memory store implementations serve as the reference for expected behavior
- Optional backends (MongoDB, Neo4j, DynamoDB) are explicitly out of scope for this feature
