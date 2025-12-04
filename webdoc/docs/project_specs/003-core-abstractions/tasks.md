# Tasks: Core Abstractions Layer

**Input**: Design documents from `/specs/003-core-abstractions/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Test tasks are included as this is a foundational layer requiring thorough validation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Source**: `soldier/` package at repository root
- **Tests**: `tests/unit/` and `tests/integration/` at repository root
- Paths match structure defined in plan.md

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add required dependencies and configure project for this feature

- [x] T001 Add observability dependencies (structlog, prometheus_client) to pyproject.toml
- [x] T002 Add OpenTelemetry dependencies (opentelemetry-sdk, opentelemetry-exporter-otlp) to pyproject.toml
- [x] T003 Add pytest-asyncio dependency for async tests to pyproject.toml
- [x] T004 [P] Create soldier/observability/__init__.py package file
- [x] T005 [P] Create tests/unit/observability/__init__.py package file
- [x] T006 [P] Create tests/unit/providers/__init__.py package file

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Base models and enums that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T007 Define TenantScopedModel and AgentScopedModel base classes in soldier/alignment/models/base.py
- [x] T008 Define Scope enum (GLOBAL, SCENARIO, STEP) in soldier/alignment/models/enums.py
- [x] T009 [P] Define Channel enum (WHATSAPP, SLACK, WEBCHAT, EMAIL, VOICE, API) in soldier/conversation/models/enums.py
- [x] T010 [P] Define SessionStatus enum (ACTIVE, IDLE, PROCESSING, INTERRUPTED, CLOSED) in soldier/conversation/models/enums.py
- [x] T011 [P] Define ProfileFieldSource enum in soldier/profile/enums.py
- [x] T012 [P] Define VerificationLevel enum in soldier/profile/enums.py
- [x] T013 Create shared vector similarity helper function in soldier/utils/vector.py (cosine_similarity)
- [x] T014 [P] Create tests for base models in tests/unit/alignment/test_base_models.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Developer Debugging with Structured Logs (Priority: P1) 🎯 MVP

**Goal**: Provide structured JSON logging with context binding and PII redaction

**Independent Test**: Initialize logging, emit log with bound context, verify JSON output contains all fields

### Tests for User Story 1

- [x] T015 [P] [US1] Create test for JSON log output format in tests/unit/observability/test_logging.py
- [x] T016 [P] [US1] Create test for console log output format in tests/unit/observability/test_logging.py
- [x] T017 [P] [US1] Create test for context binding (tenant_id, agent_id, etc.) in tests/unit/observability/test_logging.py
- [x] T018 [P] [US1] Create test for PII redaction (email, phone, SSN) in tests/unit/observability/test_logging.py

### Implementation for User Story 1

- [x] T019 [US1] Implement setup_logging() function with format selection in soldier/observability/logging.py
- [x] T020 [US1] Implement get_logger() function returning bound logger in soldier/observability/logging.py
- [x] T021 [US1] Implement PII redaction processor with regex patterns in soldier/observability/logging.py
- [x] T022 [US1] Implement context binding via structlog.contextvars in soldier/observability/logging.py
- [x] T023 [US1] Export logging functions from soldier/observability/__init__.py

**Checkpoint**: Structured logging with context and PII redaction is functional

---

## Phase 4: User Story 2 - Operator Monitoring System Health (Priority: P1)

**Goal**: Expose Prometheus-compatible metrics for request counts, latencies, and errors

**Independent Test**: Simulate operations, verify metrics increment correctly, scrape /metrics endpoint

### Tests for User Story 2

- [x] T024 [P] [US2] Create test for counter increment in tests/unit/observability/test_metrics.py
- [x] T025 [P] [US2] Create test for histogram observation in tests/unit/observability/test_metrics.py
- [x] T026 [P] [US2] Create test for gauge set/get in tests/unit/observability/test_metrics.py
- [x] T027 [P] [US2] Create test for metrics export format in tests/unit/observability/test_metrics.py

### Implementation for User Story 2

- [x] T028 [US2] Define REQUEST_COUNT counter with labels in soldier/observability/metrics.py
- [x] T029 [US2] Define REQUEST_LATENCY histogram with buckets in soldier/observability/metrics.py
- [x] T030 [US2] Define LLM_TOKENS counter with direction label in soldier/observability/metrics.py
- [x] T031 [US2] Define RULES_MATCHED histogram in soldier/observability/metrics.py
- [x] T032 [US2] Define ACTIVE_SESSIONS gauge in soldier/observability/metrics.py
- [x] T033 [US2] Define ERRORS counter with error_type label in soldier/observability/metrics.py
- [x] T034 [US2] Implement setup_metrics() initialization function in soldier/observability/metrics.py
- [x] T035 [US2] Export metrics functions from soldier/observability/__init__.py

**Checkpoint**: Prometheus metrics available for request monitoring

---

## Phase 5: User Story 3 - Developer Creating and Validating Domain Entities (Priority: P1)

**Goal**: All Pydantic domain models with validation, defaults, and serialization

**Independent Test**: Instantiate each model with valid/invalid data, verify validation behavior

### Tests for User Story 3

- [x] T036 [P] [US3] Create tests for Rule model validation in tests/unit/alignment/test_models.py
- [x] T037 [P] [US3] Create tests for Scenario/ScenarioStep models in tests/unit/alignment/test_models.py
- [x] T038 [P] [US3] Create tests for Template/Variable models in tests/unit/alignment/test_models.py
- [x] T039 [P] [US3] Create tests for Episode/Entity/Relationship models in tests/unit/memory/test_models.py
- [x] T040 [P] [US3] Create tests for Session/Turn models in tests/unit/conversation/test_models.py
- [x] T041 [P] [US3] Create tests for TurnRecord/AuditEvent models in tests/unit/audit/test_models.py
- [x] T042 [P] [US3] Create tests for CustomerProfile/ProfileField models in tests/unit/profile/test_models.py

### Implementation for User Story 3 - Alignment Domain

- [x] T043 [P] [US3] Implement Rule model with validation (priority -100 to 100) in soldier/alignment/models/rule.py
- [x] T044 [P] [US3] Implement MatchedRule model in soldier/alignment/models/rule.py
- [x] T045 [P] [US3] Implement Scenario model with version tracking in soldier/alignment/models/scenario.py
- [x] T046 [P] [US3] Implement ScenarioStep model with transitions in soldier/alignment/models/scenario.py
- [x] T047 [P] [US3] Implement StepTransition model in soldier/alignment/models/scenario.py
- [x] T048 [P] [US3] Implement Template model with TemplateMode enum in soldier/alignment/models/template.py
- [x] T049 [P] [US3] Implement Variable model with VariableUpdatePolicy enum in soldier/alignment/models/variable.py
- [x] T050 [P] [US3] Implement Context, UserIntent, ExtractedEntities in soldier/alignment/models/context.py
- [x] T051 [US3] Export all alignment models from soldier/alignment/models/__init__.py

### Implementation for User Story 3 - Memory Domain

- [x] T052 [P] [US3] Implement Episode model with bi-temporal fields in soldier/memory/models/episode.py
- [x] T053 [P] [US3] Implement Entity model with temporal validity in soldier/memory/models/entity.py
- [x] T054 [P] [US3] Implement Relationship model in soldier/memory/models/relationship.py
- [x] T055 [US3] Export all memory models from soldier/memory/models/__init__.py

### Implementation for User Story 3 - Conversation Domain

- [x] T056 [P] [US3] Implement Session model with scenario tracking in soldier/conversation/models/session.py
- [x] T057 [P] [US3] Implement StepVisit model in soldier/conversation/models/session.py
- [x] T058 [P] [US3] Implement Turn model with tool calls in soldier/conversation/models/turn.py
- [x] T059 [P] [US3] Implement ToolCall model in soldier/conversation/models/turn.py
- [x] T060 [US3] Export all conversation models from soldier/conversation/models/__init__.py

### Implementation for User Story 3 - Audit Domain

- [x] T061 [P] [US3] Implement TurnRecord model in soldier/audit/models/turn_record.py
- [x] T062 [P] [US3] Implement AuditEvent model in soldier/audit/models/event.py
- [x] T063 [US3] Export all audit models from soldier/audit/models/__init__.py

### Implementation for User Story 3 - Profile Domain

- [x] T064 [P] [US3] Implement CustomerProfile model in soldier/profile/models.py
- [x] T065 [P] [US3] Implement ProfileField model with provenance in soldier/profile/models.py
- [x] T066 [P] [US3] Implement ChannelIdentity model in soldier/profile/models.py
- [x] T067 [P] [US3] Implement ProfileAsset model in soldier/profile/models.py
- [x] T068 [P] [US3] Implement Consent model in soldier/profile/models.py

**Checkpoint**: All domain models defined with full validation

---

## Phase 6: User Story 4 - Developer Storing and Retrieving Configuration (Priority: P2)

**Goal**: ConfigStore interface and InMemoryConfigStore for rules, scenarios, templates, variables

**Independent Test**: CRUD operations on in-memory store, verify tenant isolation

### Tests for User Story 4

- [x] T069 [P] [US4] Create contract tests for ConfigStore in tests/unit/alignment/stores/test_config_store_contract.py
- [x] T070 [P] [US4] Create tests for rule CRUD in InMemoryConfigStore in tests/unit/alignment/stores/test_inmemory_config.py
- [x] T071 [P] [US4] Create tests for vector search in InMemoryConfigStore in tests/unit/alignment/stores/test_inmemory_config.py
- [x] T072 [P] [US4] Create tests for tenant isolation in tests/unit/alignment/stores/test_inmemory_config.py

### Implementation for User Story 4

- [x] T073 [US4] Define ConfigStore ABC with all abstract methods in soldier/alignment/stores/config_store.py
- [x] T074 [US4] Implement InMemoryConfigStore rule methods (get_rules, get_rule, save_rule, delete_rule) in soldier/alignment/stores/inmemory.py
- [x] T075 [US4] Implement vector_search_rules with cosine similarity in soldier/alignment/stores/inmemory.py
- [x] T076 [US4] Implement InMemoryConfigStore scenario methods in soldier/alignment/stores/inmemory.py
- [x] T077 [US4] Implement InMemoryConfigStore template methods in soldier/alignment/stores/inmemory.py
- [x] T078 [US4] Implement InMemoryConfigStore variable methods in soldier/alignment/stores/inmemory.py
- [x] T079 [US4] Implement InMemoryConfigStore agent methods in soldier/alignment/stores/inmemory.py
- [x] T080 [US4] Export store classes from soldier/alignment/stores/__init__.py

**Checkpoint**: ConfigStore functional with in-memory backend

---

## Phase 7: User Story 5 - Developer Storing and Retrieving Memory (Priority: P2)

**Goal**: MemoryStore interface and InMemoryMemoryStore for episodes, entities, relationships

**Independent Test**: Add episodes/entities, verify vector search and graph traversal

### Tests for User Story 5

- [x] T081 [P] [US5] Create contract tests for MemoryStore in tests/unit/memory/stores/test_memory_store_contract.py
- [x] T082 [P] [US5] Create tests for episode CRUD and search in tests/unit/memory/stores/test_inmemory_memory.py
- [x] T083 [P] [US5] Create tests for entity/relationship operations in tests/unit/memory/stores/test_inmemory_memory.py
- [x] T084 [P] [US5] Create tests for graph traversal in tests/unit/memory/stores/test_inmemory_memory.py

### Implementation for User Story 5

- [x] T085 [US5] Define MemoryStore ABC with all abstract methods in soldier/memory/store.py
- [x] T086 [US5] Implement InMemoryMemoryStore episode methods in soldier/memory/stores/inmemory.py
- [x] T087 [US5] Implement vector_search_episodes with cosine similarity in soldier/memory/stores/inmemory.py
- [x] T088 [US5] Implement text_search_episodes with substring matching in soldier/memory/stores/inmemory.py
- [x] T089 [US5] Implement entity methods (add_entity, get_entity, get_entities) in soldier/memory/stores/inmemory.py
- [x] T090 [US5] Implement relationship methods in soldier/memory/stores/inmemory.py
- [x] T091 [US5] Implement traverse_from_entities with BFS traversal in soldier/memory/stores/inmemory.py
- [x] T092 [US5] Implement delete_by_group cleanup in soldier/memory/stores/inmemory.py
- [x] T093 [US5] Export store classes from soldier/memory/stores/__init__.py

**Checkpoint**: MemoryStore functional with graph traversal

---

## Phase 8: User Story 6 - Developer Managing Session State (Priority: P2)

**Goal**: SessionStore interface and InMemorySessionStore for session management

**Independent Test**: Session CRUD, verify state persistence and agent listing

### Tests for User Story 6

- [x] T094 [P] [US6] Create contract tests for SessionStore in tests/unit/conversation/stores/test_session_store_contract.py
- [x] T095 [P] [US6] Create tests for session CRUD in tests/unit/conversation/stores/test_inmemory_session.py
- [x] T096 [P] [US6] Create tests for get_by_channel in tests/unit/conversation/stores/test_inmemory_session.py
- [x] T097 [P] [US6] Create tests for list_by_agent in tests/unit/conversation/stores/test_inmemory_session.py

### Implementation for User Story 6

- [x] T098 [US6] Define SessionStore ABC with all abstract methods in soldier/conversation/store.py
- [x] T099 [US6] Implement InMemorySessionStore get/save/delete methods in soldier/conversation/stores/inmemory.py
- [x] T100 [US6] Implement get_by_channel lookup in soldier/conversation/stores/inmemory.py
- [x] T101 [US6] Implement list_by_agent with filtering in soldier/conversation/stores/inmemory.py
- [x] T102 [US6] Implement list_by_customer lookup in soldier/conversation/stores/inmemory.py
- [x] T103 [US6] Export store classes from soldier/conversation/stores/__init__.py

**Checkpoint**: SessionStore functional with channel lookup

---

## Phase 9: User Story 7 - Developer Recording Audit Events (Priority: P2)

**Goal**: AuditStore interface and InMemoryAuditStore for turn records and events

**Independent Test**: Save turn records, query by session and time range

### Tests for User Story 7

- [x] T104 [P] [US7] Create contract tests for AuditStore in tests/unit/audit/stores/test_audit_store_contract.py
- [x] T105 [P] [US7] Create tests for turn record CRUD in tests/unit/audit/stores/test_inmemory_audit.py
- [x] T106 [P] [US7] Create tests for list_turns queries in tests/unit/audit/stores/test_inmemory_audit.py
- [x] T107 [P] [US7] Create tests for audit event operations in tests/unit/audit/stores/test_inmemory_audit.py

### Implementation for User Story 7

- [x] T108 [US7] Define AuditStore ABC with all abstract methods in soldier/audit/store.py
- [x] T109 [US7] Implement InMemoryAuditStore turn methods in soldier/audit/stores/inmemory.py
- [x] T110 [US7] Implement list_turns_by_session with pagination in soldier/audit/stores/inmemory.py
- [x] T111 [US7] Implement list_turns_by_tenant with time filtering in soldier/audit/stores/inmemory.py
- [x] T112 [US7] Implement event methods in soldier/audit/stores/inmemory.py
- [x] T113 [US7] Export store classes from soldier/audit/stores/__init__.py

**Checkpoint**: AuditStore functional with time-series queries

---

## Phase 10: User Story 8 - Developer Managing Customer Profiles (Priority: P2)

**Goal**: ProfileStore interface and InMemoryProfileStore for customer profiles

**Independent Test**: Profile CRUD, channel identity lookup, field updates

### Tests for User Story 8

- [x] T114 [P] [US8] Create contract tests for ProfileStore in tests/unit/profile/stores/test_profile_store_contract.py
- [x] T115 [P] [US8] Create tests for profile CRUD in tests/unit/profile/stores/test_inmemory_profile.py
- [x] T116 [P] [US8] Create tests for get_or_create behavior in tests/unit/profile/stores/test_inmemory_profile.py
- [x] T117 [P] [US8] Create tests for field/asset operations in tests/unit/profile/stores/test_inmemory_profile.py

### Implementation for User Story 8

- [x] T118 [US8] Define ProfileStore ABC with all abstract methods in soldier/profile/store.py
- [x] T119 [US8] Implement InMemoryProfileStore get methods in soldier/profile/stores/inmemory.py
- [x] T120 [US8] Implement get_or_create with channel lookup in soldier/profile/stores/inmemory.py
- [x] T121 [US8] Implement update_field with provenance tracking in soldier/profile/stores/inmemory.py
- [x] T122 [US8] Implement add_asset method in soldier/profile/stores/inmemory.py
- [x] T123 [US8] Implement link_channel method in soldier/profile/stores/inmemory.py
- [x] T124 [US8] Implement merge_profiles method in soldier/profile/stores/inmemory.py
- [x] T125 [US8] Export store classes from soldier/profile/stores/__init__.py

**Checkpoint**: ProfileStore functional with channel identity management

---

## Phase 11: User Story 9 - Developer Using LLM for Text Generation (Priority: P2)

**Goal**: LLMProvider interface and MockLLMProvider for testing

**Independent Test**: Call mock provider, verify configurable responses and token usage

### Tests for User Story 9

- [x] T126 [P] [US9] Create tests for LLMProvider interface in tests/unit/providers/test_llm_mock.py
- [x] T127 [P] [US9] Create tests for MockLLMProvider generate() in tests/unit/providers/test_llm_mock.py
- [x] T128 [P] [US9] Create tests for generate_structured() in tests/unit/providers/test_llm_mock.py
- [x] T129 [P] [US9] Create tests for token usage tracking in tests/unit/providers/test_llm_mock.py

### Implementation for User Story 9

- [x] T130 [US9] Define LLMProvider ABC in soldier/providers/llm/base.py
- [x] T131 [US9] Define LLMResponse and TokenUsage models in soldier/providers/llm/base.py
- [x] T132 [US9] Implement MockLLMProvider with default_response in soldier/providers/llm/mock.py
- [x] T133 [US9] Implement generate() with token usage simulation in soldier/providers/llm/mock.py
- [x] T134 [US9] Implement generate_structured() with schema validation in soldier/providers/llm/mock.py
- [x] T135 [US9] Add call_history tracking to MockLLMProvider in soldier/providers/llm/mock.py
- [x] T136 [US9] Export LLM provider classes from soldier/providers/llm/__init__.py

**Checkpoint**: LLMProvider functional with mock implementation

---

## Phase 12: User Story 10 - Developer Using Embeddings for Semantic Search (Priority: P2)

**Goal**: EmbeddingProvider interface and MockEmbeddingProvider for testing

**Independent Test**: Embed text, verify vector dimensions and deterministic output

### Tests for User Story 10

- [x] T137 [P] [US10] Create tests for EmbeddingProvider interface in tests/unit/providers/test_embedding_mock.py
- [x] T138 [P] [US10] Create tests for embed() dimensions in tests/unit/providers/test_embedding_mock.py
- [x] T139 [P] [US10] Create tests for embed_batch() in tests/unit/providers/test_embedding_mock.py
- [x] T140 [P] [US10] Create tests for deterministic output in tests/unit/providers/test_embedding_mock.py

### Implementation for User Story 10

- [x] T141 [US10] Define EmbeddingProvider ABC with dimensions property in soldier/providers/embedding/base.py
- [x] T142 [US10] Implement MockEmbeddingProvider with configurable dimensions in soldier/providers/embedding/mock.py
- [x] T143 [US10] Implement deterministic embed() based on text hash in soldier/providers/embedding/mock.py
- [x] T144 [US10] Implement embed_batch() for efficient batch processing in soldier/providers/embedding/mock.py
- [x] T145 [US10] Export embedding provider classes from soldier/providers/embedding/__init__.py

**Checkpoint**: EmbeddingProvider functional with deterministic mock

---

## Phase 13: User Story 11 - Developer Reranking Search Results (Priority: P3)

**Goal**: RerankProvider interface and MockRerankProvider for testing

**Independent Test**: Rerank documents, verify score ordering

### Tests for User Story 11

- [x] T146 [P] [US11] Create tests for RerankProvider interface in tests/unit/providers/test_rerank_mock.py
- [x] T147 [P] [US11] Create tests for rerank() score ordering in tests/unit/providers/test_rerank_mock.py
- [x] T148 [P] [US11] Create tests for top_k parameter in tests/unit/providers/test_rerank_mock.py

### Implementation for User Story 11

- [x] T149 [US11] Define RerankProvider ABC in soldier/providers/rerank/base.py
- [x] T150 [US11] Define RerankResult model in soldier/providers/rerank/base.py
- [x] T151 [US11] Implement MockRerankProvider with score strategies in soldier/providers/rerank/mock.py
- [x] T152 [US11] Implement rerank() with position-based scoring in soldier/providers/rerank/mock.py
- [x] T153 [US11] Export rerank provider classes from soldier/providers/rerank/__init__.py

**Checkpoint**: RerankProvider functional with mock

---

## Phase 14: User Story 12 - SRE Tracing Request Flow (Priority: P3)

**Goal**: OpenTelemetry tracing with span creation and context propagation

**Independent Test**: Create spans, verify parent-child relationships and attributes

### Tests for User Story 12

- [x] T154 [P] [US12] Create tests for setup_tracing() in tests/unit/observability/test_tracing.py
- [x] T155 [P] [US12] Create tests for span creation in tests/unit/observability/test_tracing.py
- [x] T156 [P] [US12] Create tests for span hierarchy in tests/unit/observability/test_tracing.py
- [x] T157 [P] [US12] Create tests for trace propagation in tests/unit/observability/test_tracing.py

### Implementation for User Story 12

- [x] T158 [US12] Implement setup_tracing() with OTLP exporter and W3C traceparent context extraction in soldier/observability/tracing.py
- [x] T159 [US12] Implement get_tracer() function in soldier/observability/tracing.py
- [x] T160 [US12] Implement span() context manager in soldier/observability/tracing.py
- [x] T161 [US12] Implement add_span_attributes() helper in soldier/observability/tracing.py
- [x] T162 [US12] Define standard span attributes (ATTR_TENANT_ID, etc.) in soldier/observability/tracing.py
- [x] T163 [US12] Export tracing functions from soldier/observability/__init__.py

**Checkpoint**: OpenTelemetry tracing functional

---

## Phase 15: Polish & Cross-Cutting Concerns

**Purpose**: Provider factory, middleware, and integration tests

- [x] T164 [P] Implement create_llm_provider() factory in soldier/providers/factory.py
- [x] T165 [P] Implement create_embedding_provider() factory in soldier/providers/factory.py
- [x] T166 [P] Implement create_rerank_provider() factory in soldier/providers/factory.py
- [x] T167 [P] Define provider config models in soldier/providers/factory.py
- [x] T168 [P] Create tests for provider factory in tests/unit/providers/test_factory.py
- [x] T169 Implement observability_middleware with context binding in soldier/observability/middleware.py
- [x] T170 [P] Create tests for middleware in tests/unit/observability/test_middleware.py
- [x] T171 Create integration test for all stores contract in tests/integration/test_stores_contract.py
- [x] T172 Export all providers from soldier/providers/__init__.py
- [x] T173 Run full test suite and verify 85% coverage
- [x] T174 Validate quickstart.md examples work correctly

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Story 1-3 (P1)**: Can start after Foundational - form MVP core
- **User Story 4-10 (P2)**: Can start after Foundational - stores and providers
- **User Story 11-12 (P3)**: Can start after Foundational - optional enhancements
- **Polish (Phase 15)**: Depends on all stories being complete

### User Story Dependencies

| Story | Priority | Depends On | Provides |
|-------|----------|------------|----------|
| US1 (Logging) | P1 | Foundational | Structured logging for all other stories |
| US2 (Metrics) | P1 | Foundational | Metrics instrumentation |
| US3 (Models) | P1 | Foundational | All domain models for stores |
| US4 (ConfigStore) | P2 | US3 (models) | Rule/scenario storage |
| US5 (MemoryStore) | P2 | US3 (models) | Episode/entity storage |
| US6 (SessionStore) | P2 | US3 (models) | Session management |
| US7 (AuditStore) | P2 | US3 (models) | Audit trail |
| US8 (ProfileStore) | P2 | US3 (models) | Customer profiles |
| US9 (LLMProvider) | P2 | Foundational | Text generation |
| US10 (Embeddings) | P2 | Foundational | Vector embeddings |
| US11 (Rerank) | P3 | Foundational | Result reranking |
| US12 (Tracing) | P3 | US1 (logging) | Distributed tracing |

### Parallel Opportunities

**Within Foundational (Phase 2)**:
- T009, T010, T011, T012 (all enums) can run in parallel
- T014 (base model tests) can run with enum tasks

**Within User Story 3 (Models)**:
- All model implementation tasks (T043-T068) can run in parallel
- All model test tasks (T036-T042) can run in parallel

**User Stories 4-10 (Stores/Providers)**:
- After US3 models are complete, all stores can be implemented in parallel
- All provider stories (US9, US10, US11) can run in parallel

---

## Parallel Example: User Story 3 (Domain Models)

```bash
# Launch all model tests in parallel:
Task: "Create tests for Rule model in tests/unit/alignment/test_models.py"
Task: "Create tests for Episode/Entity models in tests/unit/memory/test_models.py"
Task: "Create tests for Session/Turn models in tests/unit/conversation/test_models.py"
Task: "Create tests for CustomerProfile models in tests/unit/profile/test_models.py"

# Then launch all model implementations in parallel:
Task: "Implement Rule model in soldier/alignment/models/rule.py"
Task: "Implement Episode model in soldier/memory/models/episode.py"
Task: "Implement Session model in soldier/conversation/models/session.py"
Task: "Implement CustomerProfile model in soldier/profile/models.py"
```

---

## Parallel Example: All Stores (After US3)

```bash
# Launch all store implementations in parallel:
Task: "Implement InMemoryConfigStore in soldier/alignment/stores/inmemory.py"
Task: "Implement InMemoryMemoryStore in soldier/memory/stores/inmemory.py"
Task: "Implement InMemorySessionStore in soldier/conversation/stores/inmemory.py"
Task: "Implement InMemoryAuditStore in soldier/audit/stores/inmemory.py"
Task: "Implement InMemoryProfileStore in soldier/profile/stores/inmemory.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1-3 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US1 - Structured Logging
4. Complete Phase 4: US2 - Metrics
5. Complete Phase 5: US3 - Domain Models
6. **STOP and VALIDATE**: All models exist, logging/metrics work
7. Foundation is complete for building alignment pipeline

### Incremental Delivery

1. Complete Setup + Foundational → Base ready
2. Add US1-US3 → Observability + Models (MVP!)
3. Add US4-US8 → All stores functional
4. Add US9-US10 → Providers for alignment
5. Add US11-US12 → Optional enhancements
6. Each increment enables more features

### Suggested MVP Scope

**Minimum**: User Stories 1-3 (Logging, Metrics, Models)
- Provides: Structured logging, Prometheus metrics, all domain models
- Enables: Building alignment pipeline with basic debugging

**Recommended**: User Stories 1-5 (add ConfigStore, MemoryStore)
- Provides: All above + configuration and memory storage
- Enables: Full rule/scenario management, memory operations

---

## Notes

- [P] tasks = different files, no dependencies
- [US#] label maps task to specific user story
- Each store has its own contract test file for reuse with production implementations
- Mock providers track call history for test assertions
- All async methods use pytest-asyncio
- Run `uv run pytest --cov=soldier --cov-report=term-missing` to verify coverage
