# Tasks: Customer Context Vault (Hybrid Design)

**Input**: Design documents from `/specs/010-customer-context-vault/`
**Prerequisites**: plan.md, spec.md, research.md, contracts/data-model.md, contracts/store-interfaces.md

**Tests**: Included per spec NFR Validation Methodology and constitution testing requirements.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story (e.g., US1, US2..., US7)
- Paths use Soldier's existing structure: `soldier/`, `tests/`

## Path Conventions

Single backend project per plan.md:
- Source: `soldier/profile/`, `soldier/jobs/`, `soldier/db/migrations/`
- Tests: `tests/unit/`, `tests/contract/`, `tests/integration/`, `tests/performance/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and dependencies

- [x] T001 Add hatchet-sdk dependency via `uv add hatchet-sdk` in pyproject.toml
- [x] T002 [P] Add Hatchet services to docker-compose.yml (hatchet-engine, hatchet-api)
- [x] T003 [P] Create HatchetConfig model in soldier/config/models/jobs.py
- [x] T004 [P] Add [jobs.hatchet] section to config/default.toml
- [x] T005 [P] Create soldier/jobs/__init__.py module structure
- [x] T006 [P] Create soldier/jobs/workflows/__init__.py module structure

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core enums and models that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

### 2.1 Enums (Required by all models)

- [x] T007 [P] Add ItemStatus enum (active, superseded, expired, orphaned) to soldier/profile/enums.py
- [x] T008 [P] Add SourceType enum (profile_field, profile_asset, session, tool, external) to soldier/profile/enums.py
- [x] T009 [P] Add RequiredLevel enum (hard, soft) to soldier/profile/enums.py
- [x] T010 [P] Add FallbackAction enum (ask, skip, block, extract) to soldier/profile/enums.py
- [x] T011 [P] Add ValidationMode enum (strict, warn, disabled) to soldier/profile/enums.py

### 2.2 Enhanced Models

- [x] T012 Enhance ProfileField model with lineage fields (id, source_item_id, source_item_type, source_metadata) in soldier/profile/models.py
- [x] T013 Enhance ProfileField model with status fields (status, superseded_by_id, superseded_at) in soldier/profile/models.py
- [x] T014 Add is_orphaned computed property to ProfileField in soldier/profile/models.py
- [x] T015 Enhance ProfileAsset model with lineage fields (source_item_id, source_item_type, derived_from_tool) in soldier/profile/models.py
- [x] T016 Enhance ProfileAsset model with status fields (status, superseded_by_id, superseded_at, analysis_field_ids) in soldier/profile/models.py
- [x] T017 Add is_orphaned computed property to ProfileAsset in soldier/profile/models.py

### 2.3 New Schema Models

- [x] T018 [P] Create ProfileFieldDefinition model per contracts/data-model.md in soldier/profile/models.py
- [x] T019 [P] Create ScenarioFieldRequirement model per contracts/data-model.md in soldier/profile/models.py

### 2.4 Unit Tests for Models

- [x] T020 [P] Create tests/unit/profile/test_models.py with ItemStatus enum tests
- [x] T021 [P] Add ProfileField lineage and status tests to tests/unit/profile/test_models.py
- [x] T022 [P] Add ProfileAsset lineage and status tests to tests/unit/profile/test_models.py
- [x] T023 [P] Add ProfileFieldDefinition validation tests to tests/unit/profile/test_models.py
- [x] T024 [P] Add ScenarioFieldRequirement validation tests to tests/unit/profile/test_models.py

**Checkpoint**: Foundation ready - all enums, enhanced models, and schema models complete

---

## Phase 3: User Story 1 - Lineage Tracking for Derived Data (Priority: P1)

**Goal**: Trace how any piece of customer data was derived (source_item_id chains)

**Independent Test**: Upload asset, run analysis tool, verify analysis result links back via source_item_id

### Contract Tests for US1

- [x] T025 [P] [US1] Contract test get_derivation_chain() in tests/contract/test_profile_store_contract.py
- [x] T026 [P] [US1] Contract test get_derived_items() in tests/contract/test_profile_store_contract.py
- [x] T027 [P] [US1] Contract test check_has_dependents() in tests/contract/test_profile_store_contract.py
- [x] T028 [P] [US1] Contract test circular reference detection (max depth 10) in tests/contract/test_profile_store_contract.py

### Store Interface Updates for US1

- [x] T029 [US1] Add get_derivation_chain(tenant_id, item_id, item_type) method to ProfileStore ABC in soldier/profile/store.py
- [x] T030 [US1] Add get_derived_items(tenant_id, source_item_id) method to ProfileStore ABC in soldier/profile/store.py
- [x] T031 [US1] Add check_has_dependents(tenant_id, item_id) method to ProfileStore ABC in soldier/profile/store.py

### InMemoryProfileStore for US1

- [x] T032 [US1] Implement get_derivation_chain() in InMemoryProfileStore in soldier/profile/stores/inmemory.py
- [x] T033 [US1] Implement get_derived_items() in InMemoryProfileStore in soldier/profile/stores/inmemory.py
- [x] T034 [US1] Implement check_has_dependents() in InMemoryProfileStore in soldier/profile/stores/inmemory.py

### Unit Tests for US1

- [x] T035 [P] [US1] Unit test get_derivation_chain() up to 10 levels in tests/unit/profile/stores/test_inmemory_profile.py
- [x] T036 [P] [US1] Unit test circular reference detection in tests/unit/profile/stores/test_inmemory_profile.py
- [x] T037 [P] [US1] Unit test get_derived_items() in tests/unit/profile/stores/test_inmemory_profile.py

**Checkpoint**: US1 complete - lineage traversal works end-to-end with InMemoryProfileStore

---

## Phase 4: User Story 2 - Explicit Status Management (Priority: P1)

**Goal**: Track status (active, superseded, expired, orphaned) with default filtering

**Independent Test**: Save new value for existing key, verify old marked superseded, get_field returns only active

### Contract Tests for US2

- [x] T038 [P] [US2] Contract test get_field() filters by status in tests/contract/test_profile_store_contract.py
- [x] T039 [P] [US2] Contract test get_field_history() returns all statuses in tests/contract/test_profile_store_contract.py
- [x] T040 [P] [US2] Contract test update_field() marks old as superseded in tests/contract/test_profile_store_contract.py
- [x] T041 [P] [US2] Contract test expire_stale_fields() in tests/contract/test_profile_store_contract.py
- [x] T042 [P] [US2] Contract test mark_orphaned_items() in tests/contract/test_profile_store_contract.py

### Store Interface Updates for US2

- [x] T043 [US2] Update get_field() to accept status filter (default=ACTIVE) in soldier/profile/store.py
- [x] T044 [US2] Add get_field_history(tenant_id, profile_id, name) method to ProfileStore ABC in soldier/profile/store.py
- [x] T045 [US2] Add expire_stale_fields(tenant_id) method to ProfileStore ABC in soldier/profile/store.py
- [x] T046 [US2] Add mark_orphaned_items(tenant_id) method to ProfileStore ABC in soldier/profile/store.py

### InMemoryProfileStore for US2

- [x] T047 [US2] Implement status-aware get_field() in InMemoryProfileStore in soldier/profile/stores/inmemory.py
- [x] T048 [US2] Implement get_field_history() in InMemoryProfileStore in soldier/profile/stores/inmemory.py
- [x] T049 [US2] Implement superseding logic in update_field() in soldier/profile/stores/inmemory.py
- [x] T050 [US2] Implement expire_stale_fields() in InMemoryProfileStore in soldier/profile/stores/inmemory.py
- [x] T051 [US2] Implement mark_orphaned_items() in InMemoryProfileStore in soldier/profile/stores/inmemory.py

### Unit Tests for US2

- [x] T052 [P] [US2] Unit test status filtering in get_field() in tests/unit/profile/stores/test_inmemory_profile.py
- [x] T053 [P] [US2] Unit test superseding behavior in tests/unit/profile/stores/test_inmemory_profile.py
- [x] T054 [P] [US2] Unit test field history returns all versions in tests/unit/profile/stores/test_inmemory_profile.py
- [x] T055 [P] [US2] Unit test expire_stale_fields() marks expired in tests/unit/profile/stores/test_inmemory_profile.py

**Checkpoint**: US2 complete - status management works end-to-end with InMemoryProfileStore

---

## Phase 5: User Story 3 - Schema-Driven Field Definitions (Priority: P1)

**Goal**: Define field schemas (ProfileFieldDefinition) and scenario requirements (ScenarioFieldRequirement)

**Independent Test**: Create field definition with validation_regex, save field, verify validation is applied

### Contract Tests for US3

- [x] T056 [P] [US3] Contract test save_field_definition() in tests/contract/test_profile_store_contract.py
- [x] T057 [P] [US3] Contract test get_field_definitions() in tests/contract/test_profile_store_contract.py
- [x] T058 [P] [US3] Contract test save_scenario_requirement() in tests/contract/test_profile_store_contract.py
- [x] T059 [P] [US3] Contract test get_scenario_requirements() in tests/contract/test_profile_store_contract.py
- [x] T060 [P] [US3] Contract test get_missing_fields() in tests/contract/test_profile_store_contract.py

### Store Interface Updates for US3

- [x] T061 [US3] Add save_field_definition(definition) method to ProfileStore ABC in soldier/profile/store.py
- [x] T062 [US3] Add get_field_definitions(tenant_id, agent_id) method to ProfileStore ABC in soldier/profile/store.py
- [x] T063 [US3] Add save_scenario_requirement(requirement) method to ProfileStore ABC in soldier/profile/store.py
- [x] T064 [US3] Add get_scenario_requirements(tenant_id, scenario_id) method to ProfileStore ABC in soldier/profile/store.py
- [x] T065 [US3] Add get_missing_fields(tenant_id, profile, scenario_id) method to ProfileStore ABC in soldier/profile/store.py

### SchemaValidationService for US3

- [x] T066 [US3] Create SchemaValidationService class in soldier/profile/validation.py
- [x] T067 [US3] Implement validate_field(field, definition) returning error list in soldier/profile/validation.py
- [x] T068 [US3] Implement type validators (string, email, phone, date, number, boolean, json) in soldier/profile/validation.py
- [x] T069 [US3] Implement regex validation in soldier/profile/validation.py
- [x] T070 [US3] Implement allowed_values validation in soldier/profile/validation.py
- [x] T071 [US3] Implement ValidationMode support (strict, warn, disabled) in soldier/profile/validation.py

### InMemoryProfileStore for US3

- [x] T072 [US3] Implement save_field_definition() in InMemoryProfileStore in soldier/profile/stores/inmemory.py
- [x] T073 [US3] Implement get_field_definitions() in InMemoryProfileStore in soldier/profile/stores/inmemory.py
- [x] T074 [US3] Implement save_scenario_requirement() in InMemoryProfileStore in soldier/profile/stores/inmemory.py
- [x] T075 [US3] Implement get_scenario_requirements() in InMemoryProfileStore in soldier/profile/stores/inmemory.py
- [x] T076 [US3] Implement get_missing_fields() in InMemoryProfileStore in soldier/profile/stores/inmemory.py

### Unit Tests for US3

- [x] T077 [P] [US3] Unit test SchemaValidationService type validation in tests/unit/profile/test_validation.py
- [x] T078 [P] [US3] Unit test regex validation in tests/unit/profile/test_validation.py
- [x] T079 [P] [US3] Unit test allowed_values validation in tests/unit/profile/test_validation.py
- [x] T080 [P] [US3] Unit test ValidationMode behaviors in tests/unit/profile/test_validation.py
- [x] T081 [P] [US3] Unit test get_missing_fields() in tests/unit/profile/stores/test_inmemory_profile.py

**Checkpoint**: US3 complete - schema definitions and validation work end-to-end

---

## Phase 6: User Story 5 - PostgreSQL Schema & Migrations (Priority: P2)

**Goal**: Alembic migrations for all profile-related tables with correct indexes

**Independent Test**: Run migrations on fresh DB, verify tables created with correct columns and indexes

### Migrations

- [x] T082 [US5] Create migration 006_profile_fields_enhancement.py (add lineage + status columns) in soldier/db/migrations/versions/
- [x] T083 [US5] Create migration 007_profile_assets_enhancement.py (add lineage + status columns) in soldier/db/migrations/versions/
- [x] T084 [US5] Create migration 008_profile_field_definitions.py (new table) in soldier/db/migrations/versions/
- [x] T085 [US5] Create migration 009_scenario_field_requirements.py (new table) in soldier/db/migrations/versions/
- [x] T086 [US5] Add rollback functions to all migrations for safe rollback

### PostgresProfileStore Implementation

- [x] T087 [US5] Implement all US1 methods (lineage) in PostgresProfileStore in soldier/profile/stores/postgres.py
- [x] T088 [US5] Implement all US2 methods (status) in PostgresProfileStore in soldier/profile/stores/postgres.py
- [x] T089 [US5] Implement all US3 methods (schema) in PostgresProfileStore in soldier/profile/stores/postgres.py
- [x] T090 [US5] Implement recursive CTE for get_derivation_chain() in soldier/profile/stores/postgres.py
- [x] T091 [US5] Add soft-delete enforcement in delete methods in soldier/profile/stores/postgres.py

### Integration Tests for US5

- [ ] T092 [P] [US5] Integration test migrations apply cleanly in tests/integration/stores/test_postgres_profile.py
- [ ] T093 [P] [US5] Integration test migrations rollback cleanly in tests/integration/stores/test_postgres_profile.py
- [ ] T094 [US5] Run contract tests against PostgresProfileStore in tests/contract/test_profile_store_contract.py

**Checkpoint**: US5 complete - PostgreSQL backend fully functional with all methods

---

## Phase 7: User Story 4 - Redis Caching for ProfileStore (Priority: P2)

**Goal**: Two-tier caching (Redis + PostgreSQL) with write-through invalidation

**Independent Test**: Load profile (cache miss), load again (cache hit), verify hit rate > 80%

### CachedProfileStore Implementation

- [x] T095 [US4] Create CachedProfileStore wrapper class in soldier/profile/stores/cached.py
- [x] T096 [US4] Implement cache-through read for get_profile() in soldier/profile/stores/cached.py
- [x] T097 [US4] Implement cache invalidation on update_field() in soldier/profile/stores/cached.py
- [x] T098 [US4] Implement cache invalidation on save_asset() in soldier/profile/stores/cached.py
- [x] T099 [US4] Implement Redis fallback (return from backend if Redis unavailable) in soldier/profile/stores/cached.py
- [x] T100 [US4] Add cache key patterns (profile:{tenant}:{customer}) in soldier/profile/stores/cached.py
- [x] T101 [US4] Add configurable TTL (default 30 min) in soldier/profile/stores/cached.py

### Cache Metrics for US4

- [x] T102 [US4] Add PROFILE_CACHE_HITS counter to soldier/observability/metrics.py
- [x] T103 [US4] Add PROFILE_CACHE_MISSES counter to soldier/observability/metrics.py
- [x] T104 [US4] Add PROFILE_CACHE_INVALIDATIONS counter to soldier/observability/metrics.py

### Unit Tests for US4

- [x] T105 [P] [US4] Unit test cache hit behavior in tests/unit/profile/stores/test_cached_profile.py
- [x] T106 [P] [US4] Unit test cache miss behavior in tests/unit/profile/stores/test_cached_profile.py
- [x] T107 [P] [US4] Unit test cache invalidation on write in tests/unit/profile/stores/test_cached_profile.py
- [x] T108 [P] [US4] Unit test Redis failure fallback in tests/unit/profile/stores/test_cached_profile.py

### Integration Tests for US4

- [ ] T109 [US4] Integration test CachedProfileStore with real Redis in tests/integration/stores/test_cached_profile.py
- [ ] T110 [US4] Integration test cache hit rate > 80% in tests/integration/stores/test_cached_profile.py
- [ ] T111 [US4] Integration test Redis failure recovery in tests/integration/stores/test_cached_profile.py

**Checkpoint**: US4 complete - caching layer functional with >80% hit rate

---

## Phase 8: User Story 6 - Background Job Infrastructure (Priority: P2)

**Goal**: Hatchet-based scheduled jobs for field expiry and orphan detection

**Independent Test**: Schedule expiry job, verify it runs and marks expired fields correctly

### Hatchet Client

- [x] T112 [US6] Create HatchetClient wrapper class in soldier/jobs/client.py
- [x] T113 [US6] Implement get_client() factory function in soldier/jobs/client.py
- [x] T114 [US6] Implement health_check() method in soldier/jobs/client.py
- [x] T115 [US6] Add graceful degradation when Hatchet unavailable in soldier/jobs/client.py

### Hatchet Workflows

- [x] T116 [US6] Create ExpireStaleFieldsWorkflow with cron schedule in soldier/jobs/workflows/profile_expiry.py
- [x] T117 [US6] Create DetectOrphanedItemsWorkflow with cron schedule in soldier/jobs/workflows/orphan_detection.py
- [x] T118 [US6] Ensure all workflows are idempotent in soldier/jobs/workflows/
- [x] T119 [US6] Add retry policy with exponential backoff to workflows

### Unit Tests for US6

- [x] T120 [P] [US6] Unit test ExpireStaleFieldsWorkflow logic in tests/unit/jobs/test_workflows.py
- [x] T121 [P] [US6] Unit test DetectOrphanedItemsWorkflow logic in tests/unit/jobs/test_workflows.py
- [x] T122 [P] [US6] Unit test workflow idempotency in tests/unit/jobs/test_workflows.py

### Integration Tests for US6

- [ ] T123 [US6] Integration test workflows run on schedule in tests/integration/jobs/test_hatchet_workflows.py
- [ ] T123a [US6] Integration test retry with exponential backoff in tests/integration/jobs/test_hatchet_workflows.py
- [ ] T124 [US6] Integration test Hatchet unavailability handling in tests/integration/jobs/test_hatchet_workflows.py

**Checkpoint**: US6 complete - background jobs functional with Hatchet

---

## Phase 9: User Story 7 - ProfileItemSchemaExtraction (Priority: P1)

**Goal**: LLM-based auto-extraction of required profile fields from scenarios/rules

**Independent Test**: Create scenario with "if customer is over 18", verify date_of_birth requirement generated

### ProfileItemSchemaExtractor Service

- [x] T125 [US7] Create ProfileItemSchemaExtractor class in soldier/profile/extraction.py
- [x] T126 [US7] Implement extract_requirements(scenario_or_rule) method in soldier/profile/extraction.py
- [x] T127 [US7] Implement suggest_field_definitions(field_names) method in soldier/profile/extraction.py
- [x] T128 [US7] Implement confidence scoring logic in soldier/profile/extraction.py
- [x] T129 [US7] Add needs_human_review flag when confidence < 0.8 in soldier/profile/extraction.py
- [x] T130 [US7] Create extraction prompt templates in soldier/profile/extraction.py

### Hatchet Workflow for US7

- [x] T131 [US7] Create ExtractSchemaRequirementsWorkflow in soldier/jobs/workflows/schema_extraction.py
- [x] T132 [US7] Add extract() step using ProfileItemSchemaExtractor
- [x] T133 [US7] Add persist() step saving requirements to store
- [x] T134 [US7] Ensure non-blocking (failures don't block scenario/rule creation)

### ConfigStore Integration

- [x] T135 [US7] Add hook to trigger extraction on Scenario create in soldier/alignment/stores/config_store_extraction.py
- [x] T136 [US7] Add hook to trigger extraction on Scenario update in soldier/alignment/stores/config_store_extraction.py
- [x] T137 [US7] Add hook to trigger extraction on Rule create in soldier/alignment/stores/config_store_extraction.py
- [x] T138 [US7] Add hook to trigger extraction on Rule update in soldier/alignment/stores/config_store_extraction.py

### Unit Tests for US7

- [x] T139 [P] [US7] Unit test extraction from scenario conditions in tests/unit/profile/test_extraction.py
- [x] T140 [P] [US7] Unit test extraction from rule conditions in tests/unit/profile/test_extraction.py
- [x] T141 [P] [US7] Unit test confidence scoring in tests/unit/profile/test_extraction.py
- [x] T142 [P] [US7] Unit test field definition suggestions in tests/unit/profile/test_extraction.py
- [x] T143 [P] [US7] Unit test needs_human_review flag in tests/unit/profile/test_extraction.py

### Integration Tests for US7 (with pytest-recording)

- [ ] T144 [US7] Integration test end-to-end extraction flow in tests/integration/profile/test_schema_extraction.py
- [ ] T145 [US7] Integration test requirements persisted correctly in tests/integration/profile/test_schema_extraction.py

**Checkpoint**: US7 complete - auto-extraction works with LLM

---

## Phase 10: Integration & GapFillService Enhancement

**Purpose**: Connect all components and enhance existing GapFillService

### GapFillService Enhancement

- [x] T146 Add schema_validator parameter to GapFillService constructor in soldier/alignment/migration/gap_fill.py
- [x] T147 Add profile_store parameter to GapFillService constructor in soldier/alignment/migration/gap_fill.py
- [x] T148 Integrate get_missing_fields() into GapFillService flow in soldier/alignment/migration/gap_fill.py
- [x] T149 Use collection_prompt from ProfileFieldDefinition in soldier/alignment/migration/gap_fill.py
- [x] T150 Track lineage (source_item_id, source_item_type) on extracted fields in soldier/alignment/migration/gap_fill.py
- [x] T151 Validate extracted values against schema before persistence in soldier/alignment/migration/gap_fill.py

### GapFillResult Enhancement

- [x] T152 Add field_definition field to GapFillResult in soldier/alignment/migration/models.py
- [x] T153 Add validation_errors field to GapFillResult in soldier/alignment/migration/models.py
- [x] T154 Add source_item_id and source_item_type fields to GapFillResult in soldier/alignment/migration/models.py

### ScenarioFilter Integration

- [x] T155 Update ScenarioFilter to check required fields via get_missing_fields() in soldier/alignment/filtering/scenario_filter.py
- [x] T156 Return missing_profile_fields in ScenarioFilter result

### Integration Tests

- [ ] T157 Integration test scenario entry blocked by missing hard fields in tests/integration/alignment/test_profile_requirements.py
- [ ] T158 Integration test gap fill finds profile data in tests/integration/alignment/test_profile_requirements.py
- [ ] T159 Integration test lineage tracking on extracted values in tests/integration/alignment/test_profile_requirements.py
- [ ] T160 Integration test schema validation on persisted values in tests/integration/alignment/test_profile_requirements.py

**Checkpoint**: Integration complete - all components work together

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Observability, documentation, performance validation

### Observability Metrics

- [x] T161 [P] Add DERIVATION_CHAIN_DEPTH histogram to soldier/observability/metrics.py
- [x] T162 [P] Add SCHEMA_VALIDATION_ERRORS counter to soldier/observability/metrics.py
- [x] T163 [P] Add FIELD_STATUS_GAUGE gauge to soldier/observability/metrics.py
- [x] T164 [P] Add GAP_FILL_ATTEMPTS counter to soldier/observability/metrics.py
- [x] T165 [P] Add SCHEMA_EXTRACTION_SUCCESS counter to soldier/observability/metrics.py
- [x] T166 [P] Add SCHEMA_EXTRACTION_FAILED counter to soldier/observability/metrics.py

### Structured Logging

- [x] T167 [P] Add profile_field_superseded log event
- [x] T168 [P] Add profile_field_expired log event
- [x] T169 [P] Add profile_field_orphaned log event
- [x] T170 [P] Add derivation_chain_traversed log event
- [x] T171 [P] Add schema_validation_failed log event
- [x] T172 [P] Add schema_extraction_completed log event

### Performance Tests

- [x] T173 Create tests/performance/test_profile_performance.py structure
- [x] T174 NFR-001 test: 1000 profile loads with warm cache < 10ms p99
- [x] T175 NFR-002 test: 1000 profile loads bypassing cache < 50ms p99
- [x] T176 NFR-003 test: 10000 field validations < 5ms p99
- [x] T177 NFR-004 test: 100 derivation chain traversals (depth 10) < 100ms p99
- [x] T178 NFR-005 test: 50 scenario extractions via LLM < 5s p99

### Documentation

- [x] T179 [P] Update docs/design/customer-profile.md with lineage section
- [x] T180 [P] Update docs/design/customer-profile.md with status section
- [x] T181 [P] Update docs/design/customer-profile.md with schema section
- [ ] T182 Validate quickstart.md examples work end-to-end

### Final Validation

- [ ] T183 Run all contract tests against PostgresProfileStore
- [ ] T184 Verify cache hit rate > 80% (SC-004)
- [ ] T185 Verify all NFR benchmarks pass
- [x] T186 Update IMPLEMENTATION_PLAN.md checkboxes for Phase 17.5

**Checkpoint**: All user stories complete, NFRs validated, documentation updated

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **US1 Lineage (Phase 3)**: Depends on Foundational
- **US2 Status (Phase 4)**: Depends on Foundational (can parallel with US1)
- **US3 Schema (Phase 5)**: Depends on Foundational (can parallel with US1, US2)
- **US5 PostgreSQL (Phase 6)**: Depends on US1, US2, US3 (needs all interface methods)
- **US4 Caching (Phase 7)**: Depends on US5 (needs PostgresProfileStore)
- **US6 Hatchet (Phase 8)**: Depends on US2 (expire, orphan methods), can parallel with US4
- **US7 Extraction (Phase 9)**: Depends on US3, US6 (needs schema + Hatchet)
- **Integration (Phase 10)**: Depends on US1-US7
- **Polish (Phase 11)**: Depends on Integration

### Critical Path

```
Setup → Foundational → (US1 ∥ US2 ∥ US3) → US5 → (US4 ∥ US6) → US7 → Integration → Polish
```

### Parallel Opportunities

**After Foundational**:
- US1 (Lineage), US2 (Status), US3 (Schema) can run in parallel

**After US5 (PostgreSQL)**:
- US4 (Caching) and US6 (Hatchet) can run in parallel

**Within each User Story**:
- Contract tests marked [P] can run in parallel
- Unit tests marked [P] can run in parallel
- Models marked [P] can run in parallel

---

## Parallel Example: User Story 1 (Lineage)

```bash
# Launch contract tests together:
Task T025: "Contract test get_derivation_chain()"
Task T026: "Contract test get_derived_items()"
Task T027: "Contract test check_has_dependents()"
Task T028: "Contract test circular reference detection"

# Launch unit tests together (after implementation):
Task T035: "Unit test get_derivation_chain() up to 10 levels"
Task T036: "Unit test circular reference detection"
Task T037: "Unit test get_derived_items()"
```

---

## Implementation Strategy

### MVP First (Recommended)

1. Complete Phases 1-2: Setup + Foundational
2. Complete Phase 3: US1 (Lineage) - P1 priority
3. Complete Phase 4: US2 (Status) - P1 priority
4. Complete Phase 5: US3 (Schema) - P1 priority
5. **STOP and VALIDATE**: All P1 stories work with InMemoryProfileStore
6. Deploy/demo MVP

### Full Implementation

1. After MVP validation, continue with:
   - Phase 6: US5 (PostgreSQL migrations + PostgresProfileStore)
   - Phase 7: US4 (Redis caching)
   - Phase 8: US6 (Hatchet background jobs)
   - Phase 9: US7 (ProfileItemSchemaExtraction)
2. Phase 10: Integration + GapFillService
3. Phase 11: Polish + NFR validation

### Task Summary

| Phase | User Story | Tasks | Parallelizable |
|-------|------------|-------|----------------|
| 1 | Setup | 6 | 5 |
| 2 | Foundational | 18 | 12 |
| 3 | US1 Lineage | 13 | 7 |
| 4 | US2 Status | 18 | 9 |
| 5 | US3 Schema | 26 | 10 |
| 6 | US5 PostgreSQL | 13 | 3 |
| 7 | US4 Caching | 17 | 8 |
| 8 | US6 Hatchet | 14 | 3 |
| 9 | US7 Extraction | 21 | 5 |
| 10 | Integration | 15 | 0 |
| 11 | Polish | 26 | 12 |
| **Total** | | **187** | **74** |

---

## Notes

- [P] tasks = different files, no dependencies between them
- [Story] label maps task to user story for traceability
- Each user story independently testable after completion
- Contract tests define expected behavior, run first
- MVP scope: Phases 1-5 (all P1 stories with InMemoryProfileStore)
- Full scope: All phases including PostgreSQL, caching, Hatchet, extraction
