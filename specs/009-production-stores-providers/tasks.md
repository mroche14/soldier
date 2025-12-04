# Tasks: Production Store & Provider Completion

**Input**: Design documents from `/specs/009-production-stores-providers/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Integration tests are core deliverables for User Stories 3, 4, and 5.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Python package**: `soldier/` at repository root
- **Tests**: `tests/` at repository root
- **Migrations**: `soldier/db/migrations/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and dependency setup

- [x] T001 Add asyncpg and pgvector dependencies to pyproject.toml
- [x] T002 Add alembic dependency to pyproject.toml
- [x] T003 [P] Update docker-compose.yml to use pgvector/pgvector:pg16 image
- [x] T004 [P] Create soldier/db/ directory structure for migrations
- [x] T005 [P] Add StoreError exception hierarchy in soldier/db/errors.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T006 Create soldier/db/alembic.ini configuration file
- [x] T007 Create soldier/db/migrations/env.py with async support
- [x] T008 [P] Create base PostgreSQL connection pool utility in soldier/db/pool.py
- [x] T009 [P] Create tests/integration/stores/conftest.py with Docker fixtures for PostgreSQL and Redis
- [x] T010 [P] Create tests/integration/providers/conftest.py with API key skip fixtures

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Redis Session Store with Two-Tier Caching (Priority: P1)

**Goal**: Implement RedisSessionStore with hot cache + persistent tier architecture

**Independent Test**: Run session CRUD operations against Redis, verify TTL behavior and tier promotion/demotion

### Implementation for User Story 1

- [x] T011 [US1] Create RedisSessionStore configuration model in soldier/config/models/storage.py (add hot_ttl, persist_ttl settings)
- [x] T012 [US1] Implement RedisSessionStore class skeleton in soldier/conversation/stores/redis.py
- [x] T013 [US1] Implement get() method with hot-first, persistent-fallback, auto-promote in soldier/conversation/stores/redis.py
- [x] T014 [US1] Implement save() method writing to hot tier with TTL in soldier/conversation/stores/redis.py
- [x] T015 [US1] Implement delete() method removing from both tiers in soldier/conversation/stores/redis.py
- [x] T016 [US1] Implement get_by_channel() with index lookup in soldier/conversation/stores/redis.py
- [x] T017 [US1] Implement list_by_agent() using index set in soldier/conversation/stores/redis.py
- [x] T018 [US1] Implement list_by_customer() using index set in soldier/conversation/stores/redis.py
- [x] T019 [US1] Implement find_sessions_by_step_hash() for migration support in soldier/conversation/stores/redis.py
- [x] T020 [US1] Implement promote_to_hot() and demote_to_persistent() helper methods in soldier/conversation/stores/redis.py
- [x] T021 [US1] Implement health_check() method in soldier/conversation/stores/redis.py
- [x] T022 [US1] Add Redis connection error handling with StoreError wrapping in soldier/conversation/stores/redis.py
- [x] T023 [US1] Add structured logging for all Redis operations in soldier/conversation/stores/redis.py

**Checkpoint**: Redis session store fully implements SessionStore interface with two-tier caching

---

## Phase 4: User Story 2 - Alembic Database Migration System (Priority: P1)

**Goal**: Set up Alembic migrations for all PostgreSQL store schemas

**Independent Test**: Run `alembic upgrade head` on empty database, verify all tables created, run `alembic downgrade -1` to verify rollback

### Implementation for User Story 2

- [x] T024 [US2] Create migration 001_initial_schema.py enabling pgvector extension in soldier/db/migrations/versions/
- [x] T025 [US2] Create migration 002_config_store.py with agents, rules, scenarios, templates, variables, tool_activations tables in soldier/db/migrations/versions/
- [x] T026 [US2] Create migration 003_memory_store.py with episodes, entities, relationships tables in soldier/db/migrations/versions/
- [x] T027 [US2] Create migration 004_audit_store.py with turn_records, audit_events tables in soldier/db/migrations/versions/
- [x] T028 [US2] Create migration 005_profile_store.py with customer_profiles, channel_identities, profile_fields, profile_assets tables in soldier/db/migrations/versions/
- [x] T029 [US2] Create migration 006_migration_plans.py with migration_plans, scenario_archives tables in soldier/db/migrations/versions/
- [x] T030 [US2] Create migration 007_vector_indexes.py with IVFFlat indexes for embeddings in soldier/db/migrations/versions/
- [x] T031 [US2] Add downgrade functions to all migration files for rollback support
- [ ] T032 [US2] Test migrations: run upgrade head, verify tables, run downgrade, verify rollback

**Checkpoint**: All PostgreSQL schemas can be created and rolled back via Alembic

---

## Phase 5: User Story 3 - PostgreSQL Store Integration Tests (Priority: P2)

**Goal**: Comprehensive integration tests for all PostgreSQL stores

**Independent Test**: Run pytest tests/integration/stores/test_postgres_*.py against Docker PostgreSQL

### Implementation for User Story 3

- [x] T033 [P] [US3] Implement PostgresConfigStore in soldier/alignment/stores/postgres.py (CRUD for agents, rules, scenarios, templates, variables)
- [x] T034 [P] [US3] Implement PostgresConfigStore vector_search_rules() with pgvector in soldier/alignment/stores/postgres.py
- [x] T035 [P] [US3] Implement PostgresMemoryStore in soldier/memory/stores/postgres.py (episodes, entities, relationships)
- [x] T036 [P] [US3] Implement PostgresMemoryStore vector_search_episodes() with pgvector in soldier/memory/stores/postgres.py
- [x] T037 [P] [US3] Implement PostgresAuditStore in soldier/audit/stores/postgres.py (turn_records, audit_events)
- [x] T038 [P] [US3] Implement PostgresProfileStore in soldier/profile/stores/postgres.py (profiles, channels, fields, assets)
- [x] T039 [US3] Create tests/integration/stores/test_postgres_config.py with CRUD and vector search tests
- [x] T040 [US3] Create tests/integration/stores/test_postgres_memory.py with episode and vector search tests
- [x] T041 [US3] Create tests/integration/stores/test_postgres_audit.py with turn record and event tests
- [x] T042 [US3] Create tests/integration/stores/test_postgres_profile.py with profile and field tests
- [x] T043 [US3] Add tenant isolation tests to all PostgreSQL store test files
- [x] T044 [US3] Add soft delete behavior tests to all PostgreSQL store test files

**Checkpoint**: All PostgreSQL stores have comprehensive integration tests passing

---

## Phase 6: User Story 4 - Redis Session Store Integration Tests (Priority: P2)

**Goal**: Integration tests for Redis session store two-tier caching

**Independent Test**: Run pytest tests/integration/stores/test_redis_session.py against Docker Redis

### Implementation for User Story 4

- [x] T045 [US4] Create tests/integration/stores/test_redis_session.py with CRUD tests
- [x] T046 [US4] Add tier promotion/demotion tests in tests/integration/stores/test_redis_session.py
- [x] T047 [US4] Add TTL expiration tests in tests/integration/stores/test_redis_session.py
- [x] T048 [US4] Add concurrent access tests in tests/integration/stores/test_redis_session.py
- [x] T049 [US4] Add index consistency tests (agent, customer, channel) in tests/integration/stores/test_redis_session.py
- [x] T050 [US4] Add connection failure handling tests in tests/integration/stores/test_redis_session.py

**Checkpoint**: Redis session store has comprehensive integration tests passing

---

## Phase 7: User Story 5 - AI Provider Integration Tests (Priority: P3)

**Goal**: Integration tests for Anthropic and OpenAI providers

**Independent Test**: Run pytest tests/integration/providers/ with API keys (skips gracefully without keys)

### Implementation for User Story 5

- [x] T051 [P] [US5] Create tests/integration/providers/test_anthropic.py with generate() test
- [x] T052 [P] [US5] Add generate_structured() test in tests/integration/providers/test_anthropic.py
- [x] T053 [P] [US5] Add system prompt test in tests/integration/providers/test_anthropic.py
- [x] T054 [P] [US5] Create tests/integration/providers/test_openai.py with generate() test
- [x] T055 [P] [US5] Add generate_structured() test in tests/integration/providers/test_openai.py
- [x] T056 [P] [US5] Add OpenAI embedding tests in tests/integration/providers/test_openai.py
- [x] T057 [US5] Add graceful skip tests when API keys missing in both provider test files
- [x] T058 [US5] Add rate limit handling tests with retry logic in both provider test files

**Checkpoint**: All provider integration tests pass (or skip gracefully without API keys)

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T059 [P] Update existing contract tests to include PostgreSQL store implementations in tests/contract/
- [x] T060 [P] Register PostgresConfigStore as 'postgres' backend in soldier/config/models/storage.py
- [x] T061 [P] Register RedisSessionStore as 'redis' backend in soldier/config/models/storage.py
- [x] T062 Update soldier/config/models/storage.py with PostgreSQL connection pool settings
- [ ] T063 Run quickstart.md validation - verify all setup steps work
- [x] T064 Update IMPLEMENTATION_PLAN.md checkboxes for Phase 16 and 17 completion

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational - Redis store implementation
- **User Story 2 (Phase 4)**: Depends on Foundational - Alembic migrations
- **User Story 3 (Phase 5)**: Depends on User Story 2 (migrations must exist for PostgreSQL stores)
- **User Story 4 (Phase 6)**: Depends on User Story 1 (Redis store must be implemented to test)
- **User Story 5 (Phase 7)**: Depends on Foundational only - provider tests independent
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational - Redis implementation
- **User Story 2 (P1)**: Can start after Foundational - Alembic migrations
- **User Story 3 (P2)**: Depends on US2 - needs migrations before PostgreSQL stores
- **User Story 4 (P2)**: Depends on US1 - needs Redis store before testing it
- **User Story 5 (P3)**: Can start after Foundational - provider tests independent of stores

### Parallel Opportunities

**Phase 1 (Setup)**:
- T003, T004, T005 can run in parallel (different files)

**Phase 2 (Foundational)**:
- T008, T009, T010 can run in parallel (different files)

**Phase 3 (US1) and Phase 4 (US2)**:
- These two phases can run in parallel after Foundational

**Phase 5 (US3)**:
- T033-T038 (store implementations) can all run in parallel
- T039-T044 (tests) should follow their respective implementations

**Phase 7 (US5)**:
- T051-T056 can all run in parallel (different test files)

---

## Parallel Example: PostgreSQL Store Implementations (Phase 5)

```bash
# Launch all PostgreSQL store implementations in parallel:
Task: "Implement PostgresConfigStore in soldier/alignment/stores/postgres.py"
Task: "Implement PostgresMemoryStore in soldier/memory/stores/postgres.py"
Task: "Implement PostgresAuditStore in soldier/audit/stores/postgres.py"
Task: "Implement PostgresProfileStore in soldier/profile/stores/postgres.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Redis session store)
4. Complete Phase 4: User Story 2 (Alembic migrations)
5. **STOP and VALIDATE**: Test Redis store manually, run migrations on empty DB
6. Deploy/demo if ready - production stores now possible

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 + 2 → Test independently → MVP ready
3. Add User Story 3 → PostgreSQL stores tested → Deploy
4. Add User Story 4 → Redis store tested → Deploy
5. Add User Story 5 → Providers tested → Full coverage

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Redis) + User Story 4 (Redis tests)
   - Developer B: User Story 2 (Migrations) + User Story 3 (PostgreSQL stores/tests)
   - Developer C: User Story 5 (Provider tests)
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- All integration tests must skip gracefully when infrastructure unavailable
