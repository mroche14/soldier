# Feature Specification: Customer Context Vault (Hybrid Design)

**Feature Branch**: `010-customer-context-vault`
**Created**: 2025-12-03
**Status**: Draft
**Input**: Evolve the existing CustomerProfile system into a comprehensive Customer Context Vault with lineage tracking, explicit status management, schema-driven field definitions, and Redis caching—combining the best of the original Soldier design with CCV proposal enhancements.

## Executive Summary

This specification defines a **hybrid approach** that:
1. **Preserves** Soldier's type-safe separate models (`ProfileField`, `ProfileAsset`)
2. **Adds** CCV's lineage tracking (`source_item_id`) for derivation chains
3. **Adds** CCV's explicit status management (`active`, `superseded`, `expired`, `orphaned`)
4. **Implements** the documented but unimplemented schema layer (`ProfileFieldDefinition`, `ScenarioFieldRequirement`)
5. **Adds** automatic ProfileItemSchemaExtraction from scenarios/rules via LLM
6. **Adds** Redis caching layer for ProfileStore (matching SessionStore pattern)
7. **Adds** Hatchet-based background job infrastructure for scheduled tasks
8. **Creates** complete PostgreSQL schema with Alembic migrations

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Lineage Tracking for Derived Data (Priority: P1)

As a compliance officer, I need to trace how any piece of customer data was derived (e.g., "KYC status came from OCR analysis of uploaded ID card") so that I can audit data provenance and explain decisions to regulators.

**Why this priority**: Lineage is critical for regulated industries (finance, healthcare). Without it, we cannot explain how derived values were computed.

**Independent Test**: Upload an asset, run analysis tool, verify the analysis result links back to the source asset via `source_item_id`.

**Acceptance Scenarios**:

1. **Given** a customer uploads an ID card image, **When** OCR analysis extracts the name, **Then** the extracted `legal_name` ProfileField has `source_item_id` pointing to the ID card ProfileAsset
2. **Given** an LLM extracts customer intent from conversation, **When** a ProfileField is created, **Then** it links to the source session/turn via `source_metadata`
3. **Given** a ProfileField with `source_item_id`, **When** I query for derivation chain, **Then** I can traverse the full lineage back to the original source
4. **Given** a source ProfileAsset is deleted, **When** I query derived fields, **Then** they have `status="orphaned"` and `is_orphaned=True` but are not auto-deleted

---

### User Story 2 - Explicit Status Management (Priority: P1)

As a data steward, I need explicit status tracking for customer data (`active`, `superseded`, `expired`) so that the system uses only current values while preserving historical data for audit.

**Why this priority**: Implicit expiry via timestamps is error-prone. Explicit status enables clear querying and prevents stale data usage.

**Acceptance Scenarios**:

1. **Given** a ProfileField with `status="active"`, **When** a new value is saved for the same key, **Then** the old field is marked `status="superseded"` and the new field is `status="active"`
2. **Given** a ProfileField past its `expires_at`, **When** the expiry job runs, **Then** the field is marked `status="expired"` (not deleted)
3. **Given** multiple versions of a field exist, **When** querying `get_field(key)`, **Then** only the `status="active"` version is returned
4. **Given** an audit request, **When** querying field history, **Then** all versions (active, superseded, expired) are returned with timestamps

---

### User Story 3 - Schema-Driven Field Definitions (Priority: P1)

As an agent designer, I need to define what customer data fields an agent can collect (schema) and which scenarios require which fields, so that the system can automatically identify missing data and collect it.

**Why this priority**: Without schema definitions, the system cannot validate what fields are expected or auto-generate collection prompts.

**Acceptance Scenarios**:

1. **Given** a `ProfileFieldDefinition` for "email" with type="email" and validation_regex, **When** a field is saved, **Then** the value is validated against the schema
2. **Given** a Scenario with required fields ["legal_name", "date_of_birth"], **When** a customer enters the scenario, **Then** missing fields are identified via `ScenarioFieldRequirement`
3. **Given** a `ProfileFieldDefinition` with `collection_prompt`, **When** the field is missing, **Then** the GapFillService uses the prompt to ask the customer
4. **Given** an LLM analyzing a scenario description, **When** `analyze_scenario_requirements()` is called, **Then** it auto-generates `ScenarioFieldRequirement` entries

---

### User Story 4 - Redis Caching for ProfileStore (Priority: P2)

As a platform operator, I need ProfileStore to use Redis caching (matching the SessionStore pattern) so that frequently accessed customer profiles don't hit the database on every request.

**Why this priority**: Profiles are accessed on every turn. Without caching, database load becomes unsustainable at scale.

**Acceptance Scenarios**:

1. **Given** a profile is loaded, **When** it's accessed again within TTL, **Then** it's served from Redis cache
2. **Given** a profile field is updated, **When** the update completes, **Then** the Redis cache is invalidated
3. **Given** Redis is unavailable, **When** profile is requested, **Then** it falls back to PostgreSQL without error
4. **Given** cache TTL expires, **When** profile is accessed, **Then** it's reloaded from PostgreSQL and re-cached

---

### User Story 5 - PostgreSQL Schema & Migrations (Priority: P2)

As a developer, I need complete Alembic migrations for all profile-related tables so that the schema can be deployed reliably to production.

**Acceptance Scenarios**:

1. **Given** a fresh database, **When** migrations run, **Then** all profile tables are created with correct indexes
2. **Given** existing profile data, **When** new columns are added via migration, **Then** data is preserved with sensible defaults
3. **Given** a migration failure, **When** rollback is triggered, **Then** schema reverts cleanly

---

### User Story 6 - Background Job Infrastructure (Priority: P2)

As a platform operator, I need scheduled background jobs (field expiry, cleanup) to run reliably across horizontally-scaled pods without duplicate execution.

**Why this priority**: Profile field expiry (FR-010) requires scheduled execution. Without proper job infrastructure, we cannot expire stale fields or run maintenance tasks.

**Independent Test**: Schedule a field expiry job, verify it runs on schedule and marks expired fields correctly.

**Acceptance Scenarios**:

1. **Given** Hatchet is configured, **When** a cron job is defined, **Then** it runs on schedule without duplicate execution across pods
2. **Given** fields with `expires_at` in the past, **When** the expiry job runs, **Then** those fields are marked `status="expired"`
3. **Given** an orphaned field (source deleted), **When** the orphan detection job runs, **Then** the field is marked `status="orphaned"`
4. **Given** Hatchet is unavailable, **When** the API receives requests, **Then** it continues serving without blocking on job submission
5. **Given** a job fails, **When** the retry policy triggers, **Then** the job is retried with exponential backoff

---

### User Story 7 - ProfileItemSchemaExtraction (Priority: P1)

As an agent designer, I need the system to automatically extract required profile fields from scenario/rule definitions so that I don't have to manually specify ScenarioFieldRequirements.

**Why this priority**: Manual specification of required fields is error-prone and tedious. Rules and scenarios already describe conditions that implicitly require profile data. LLM extraction ensures completeness.

**Independent Test**: Create a scenario with conditions like "if customer is over 18", verify the system auto-generates a requirement for "date_of_birth".

**Acceptance Scenarios**:

1. **Given** a new Scenario is created, **When** it contains conditions referencing profile fields, **Then** ProfileItemSchemaExtraction runs and generates `ScenarioFieldRequirement` entries
2. **Given** a Rule is updated, **When** its conditions change, **Then** ProfileItemSchemaExtraction re-runs and updates requirements
3. **Given** extraction has low confidence (< 0.8), **When** requirements are generated, **Then** they are flagged with `needs_human_review=True`
4. **Given** a Scenario references an undefined field, **When** extraction runs, **Then** it also generates a `ProfileFieldDefinition` suggestion
5. **Given** requirements with `needs_human_review=True`, **When** the scenario runs, **Then** it still functions (extraction is non-blocking)

---

### Edge Cases

- What happens when `source_item_id` references a non-existent item? (Field gets `status="orphaned"` and `is_orphaned` computed property returns `True`)
- How are circular derivation chains prevented? (Validation rejects self-referencing `source_item_id`, max depth enforced)
- What happens when a field is both expired AND superseded? (`superseded` takes precedence over `expired`)
- What happens when a field is orphaned AND superseded? (`superseded` takes precedence over `orphaned`)
- How does schema validation handle unknown fields? (Configurable: `strict` rejects, `warn` logs warning, `disabled` skips)
- What if Redis cache contains stale data after direct DB update? (TTL ensures eventual consistency, critical paths invalidate explicitly)
- What if ProfileItemSchemaExtraction fails? (Scenario still functions, requirements are not updated, error logged)
- What if Hatchet is unavailable? (Jobs are queued locally and retried, API continues serving)

---

## Requirements *(mandatory)*

### Functional Requirements

**Lineage Tracking**:
- **FR-001**: ProfileField MUST have optional `source_item_id: UUID | None` referencing another ProfileField or ProfileAsset
- **FR-002**: ProfileAsset MUST have optional `source_item_id: UUID | None` for asset-to-asset derivation
- **FR-003**: System MUST provide `get_derivation_chain(item_id)` to traverse lineage
- **FR-004**: System MUST track `source_type: "profile_field" | "profile_asset" | "session" | "external"` for each derived item
- **FR-005**: System MUST NOT delete items that have dependent derived items (soft-delete only)

**Status Management**:
- **FR-006**: ProfileField and ProfileAsset MUST have `status: "active" | "superseded" | "expired" | "orphaned"` field
- **FR-006a**: ProfileField and ProfileAsset MUST have computed `is_orphaned` property that returns `True` when `source_item_id` references non-existent item
- **FR-007**: Default queries MUST filter to `status="active"` only
- **FR-008**: When a new value is saved for an existing key, the old value MUST be marked `status="superseded"`
- **FR-009**: System MUST provide `get_field_history(key)` returning all versions
- **FR-010**: Background job MUST mark items past `expires_at` as `status="expired"`
- **FR-010a**: Background job MUST mark items with deleted source as `status="orphaned"`

**Schema Layer**:
- **FR-011**: System MUST implement `ProfileFieldDefinition` model per `docs/design/customer-profile.md`
- **FR-012**: System MUST implement `ScenarioFieldRequirement` model
- **FR-013**: ProfileFieldDefinition MUST include: `name`, `display_name`, `value_type`, `validation_regex`, `required_verification`, `is_pii`, `encryption_required`, `retention_days`, `collection_prompt`, `extraction_examples`
- **FR-014**: ScenarioFieldRequirement MUST include: `field_name`, `scenario_id`, `step_id` (optional), `required_level`, `fallback_action`
- **FR-015**: System MUST validate ProfileField values against ProfileFieldDefinition schema when saving
- **FR-016**: System MUST provide `get_missing_fields(scenario_id, profile)` returning unmet requirements

**Caching**:
- **FR-017**: ProfileStore MUST implement two-tier storage (Redis cache + PostgreSQL persistent)
- **FR-018**: Cache key pattern: `profile:{tenant_id}:{customer_id}`
- **FR-019**: Default cache TTL: 30 minutes (configurable)
- **FR-020**: Cache MUST be invalidated on any profile mutation
- **FR-021**: System MUST handle Redis failures gracefully (fallback to DB)

**Storage**:
- **FR-022**: System MUST provide Alembic migration for `customer_profiles` table
- **FR-023**: System MUST provide Alembic migration for `profile_fields` table with `source_item_id`, `status` columns
- **FR-024**: System MUST provide Alembic migration for `profile_assets` table with `source_item_id`, `status` columns
- **FR-025**: System MUST provide Alembic migration for `profile_field_definitions` table
- **FR-026**: System MUST provide Alembic migration for `scenario_field_requirements` table
- **FR-027**: All tables MUST have `tenant_id` column with index for multi-tenancy

**Background Jobs (Hatchet)**:
- **FR-028**: System MUST use Hatchet for background job orchestration
- **FR-029**: System MUST define `expire_stale_fields` workflow running on configurable cron schedule (default: every 5 minutes)
- **FR-030**: System MUST define `detect_orphaned_items` workflow running on configurable cron schedule (default: every 15 minutes)
- **FR-031**: Hatchet workers MUST be deployable independently of API pods
- **FR-032**: System MUST handle Hatchet unavailability gracefully (queue locally, retry)
- **FR-033**: All Hatchet tasks MUST be idempotent (safe to retry)

**ProfileItemSchemaExtraction**:
- **FR-034**: System MUST implement `ProfileItemSchemaExtractor` service using LLMExecutor
- **FR-035**: System MUST trigger extraction when a Scenario is created or updated
- **FR-036**: System MUST trigger extraction when a Rule is created or updated
- **FR-037**: Extraction MUST generate `ScenarioFieldRequirement` entries for identified profile fields
- **FR-038**: Extraction MUST set `needs_human_review=True` when confidence < 0.8
- **FR-039**: Extraction MUST suggest `ProfileFieldDefinition` when referencing undefined fields
- **FR-040**: Extraction failures MUST NOT block scenario/rule creation (non-blocking, async via Hatchet)
- **FR-041**: System MUST support configurable `validation_mode`: `strict` (reject invalid), `warn` (log warning), `disabled` (skip)

### Non-Functional Requirements

> **Note**: "Profile load" in NFR-001/NFR-002 refers to `get_by_customer_id()` returning a full `CustomerProfile` object.

- **NFR-001**: Profile load from cache MUST complete in < 10ms p99
- **NFR-002**: Profile load from PostgreSQL MUST complete in < 50ms p99
- **NFR-003**: Schema validation MUST complete in < 5ms per field
- **NFR-004**: Derivation chain traversal MUST complete in < 100ms for chains up to 10 levels deep
- **NFR-005**: ProfileItemSchemaExtraction MUST complete in < 5 seconds per scenario/rule

### NFR Validation Methodology

All performance NFRs are validated via `tests/performance/test_profile_performance.py`:

| NFR | Test Procedure | Pass Criteria |
|-----|----------------|---------------|
| NFR-001 | 1000 profile loads with warm Redis cache | p99 < 10ms |
| NFR-002 | 1000 profile loads bypassing cache (cold) | p99 < 50ms |
| NFR-003 | 10000 field validations against schema | p99 < 5ms |
| NFR-004 | 100 derivation chain traversals (max depth 10) | p99 < 100ms |
| NFR-005 | 50 scenario extractions via LLM | p99 < 5s |

Tests run in CI with Docker Compose (Redis + PostgreSQL + Hatchet).
Results exported to `benchmarks/profile_performance.json`.

### Key Entities

See `contracts/data-model.md` for full model definitions:
- `ProfileField` (enhanced with `source_item_id`, `source_type`, `status`)
- `ProfileAsset` (enhanced with `source_item_id`, `source_type`, `status`)
- `ProfileFieldDefinition` (new - schema definition)
- `ScenarioFieldRequirement` (new - scenario binding)
- `CustomerProfile` (enhanced with `field_status_summary`)

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of ProfileFields have valid `status` values after migration
- **SC-002**: Derivation chain queries return correct lineage for all test cases
- **SC-003**: Schema validation catches 100% of invalid field values in tests
- **SC-004**: Cache hit rate > 80% for profile reads in load tests
- **SC-005**: Profile read latency < 10ms p99 with warm cache
- **SC-006**: All existing ProfileStore tests pass with new implementation
- **SC-007**: GapFillService correctly identifies missing fields via ScenarioFieldRequirement

---

## Assumptions

- PostgreSQL 14+ with pgvector extension is available
- Redis 6+ is available for caching
- Hatchet (self-hosted or cloud) is available for background job orchestration
- Existing `ProfileStore` interface can be extended (not replaced)
- Existing `CustomerProfile`, `ProfileField`, `ProfileAsset` models can be extended
- The `docs/design/customer-profile.md` specification remains authoritative for field definitions
- LLMExecutor is available for ProfileItemSchemaExtraction

---

## Out of Scope

- **Unified ContextItem model**: We preserve separate `ProfileField`/`ProfileAsset` types for type safety
- **MongoDB/DynamoDB implementations**: PostgreSQL + Redis only for this phase
- **Real-time cache sync across pods**: TTL-based eventual consistency is acceptable
- **PII encryption at rest**: Handled at database level, not application level
- **GDPR data export/deletion automation**: Separate feature

---

## Dependencies

**Project-Wide Phase References** (see `IMPLEMENTATION_PLAN.md`):
- **Phase 9 (Production Stores & Providers)**: PostgresProfileStore base implementation - MUST be complete before Phase 3 (Database Schema)
- **Phase 8 (Scenario Migration)**: GapFillService integration - MUST be complete before Phase 7 (Integration)

**External Dependencies**:
- **PostgreSQL 14+**: With pgvector extension
- **Redis 6+**: For caching layer
- **Hatchet**: Self-hosted or cloud, for background job orchestration
- **Alembic**: Database migration framework (already in use)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CUSTOMER CONTEXT VAULT                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  SCHEMA LAYER (Agent-Scoped)                                         │    │
│  │                                                                       │    │
│  │  ProfileFieldDefinition          ScenarioFieldRequirement            │    │
│  │  ├─ name: "email"                ├─ scenario_id: UUID                │    │
│  │  ├─ value_type: "email"          ├─ field_name: "email"              │    │
│  │  ├─ validation_regex: ...        ├─ required_level: "hard"           │    │
│  │  ├─ collection_prompt: ...       └─ fallback_action: "ask"           │    │
│  │  └─ is_pii: true                                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  DATA LAYER (Customer-Scoped)                                        │    │
│  │                                                                       │    │
│  │  CustomerProfile                                                      │    │
│  │  ├─ fields: Dict[str, ProfileField]  ◄─── Lineage: source_item_id    │    │
│  │  │   └─ status: active|superseded|expired                            │    │
│  │  ├─ assets: List[ProfileAsset]       ◄─── Lineage: source_item_id    │    │
│  │  │   └─ status: active|superseded|expired                            │    │
│  │  ├─ channel_identities: List[ChannelIdentity]                        │    │
│  │  ├─ consents: List[Consent]                                          │    │
│  │  └─ verification_level: VerificationLevel                            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  STORAGE LAYER                                                        │    │
│  │                                                                       │    │
│  │  ┌─────────────┐    miss    ┌─────────────────┐                      │    │
│  │  │    Redis    │ ─────────► │   PostgreSQL    │                      │    │
│  │  │   (Cache)   │ ◄───────── │  (Persistent)   │                      │    │
│  │  │  TTL: 30m   │   reload   │                 │                      │    │
│  │  └─────────────┘            └─────────────────┘                      │    │
│  │        │                            │                                 │    │
│  │        └──────── invalidate ────────┘                                │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Model Enhancements
- Add `source_item_id`, `source_type`, `status` to ProfileField
- Add `source_item_id`, `source_type`, `status` to ProfileAsset
- Add `is_orphaned` computed property to ProfileField and ProfileAsset
- Implement ProfileFieldDefinition model
- Implement ScenarioFieldRequirement model
- Update unit tests

### Phase 2: Store Interface Updates
- Extend ProfileStore interface with new methods
- Implement `get_field_history()`, `get_derivation_chain()`
- Implement `get_missing_fields()` for scenario requirements
- Add schema validation hooks
- Add soft-delete enforcement (prevent hard deletes of items with dependents)

### Phase 3: Database Schema
- Create Alembic migration for profile_fields enhancements
- Create Alembic migration for profile_assets enhancements
- Create Alembic migration for profile_field_definitions
- Create Alembic migration for scenario_field_requirements
- Add indexes for lineage queries

### Phase 4: Redis Caching
- Implement CachedProfileStore wrapper
- Add cache invalidation on mutations
- Add fallback logic for Redis failures
- Configuration via TOML
- Add cache hit rate metrics collection

### Phase 5: Hatchet Background Jobs
- Configure Hatchet connection and worker
- Implement `expire_stale_fields` workflow (cron-based)
- Implement `detect_orphaned_items` workflow (cron-based)
- Add idempotency guarantees to all workflows
- Add graceful degradation for Hatchet unavailability

### Phase 6: ProfileItemSchemaExtraction
- Implement `ProfileItemSchemaExtractor` service
- Integrate with ConfigStore scenario/rule create/update hooks
- Generate ScenarioFieldRequirement from extraction results
- Generate ProfileFieldDefinition suggestions for undefined fields
- Add confidence scoring and `needs_human_review` flag

### Phase 7: Integration
- Update GapFillService to use ScenarioFieldRequirement
- Update ScenarioFilter to check required fields
- Add derivation tracking to tool execution
- Integration tests with full stack
- Redis failure recovery tests

### Phase 8: Observability & Documentation
- Add metrics for cache hit/miss ratio
- Add structured logging for lineage operations
- Add extraction success/failure metrics
- Update documentation
- Performance testing against NFRs

---

## See Also

- `docs/design/customer-profile.md` - Original design document
- `specs/008-scenario-migration/spec.md` - GapFillService integration
- `specs/009-production-stores-providers/spec.md` - PostgresProfileStore base
