# Implementation Plan: Customer Context Vault (Hybrid Design)

**Branch**: `010-customer-context-vault` | **Date**: 2025-12-03 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/010-customer-context-vault/spec.md`

## Summary

Evolve the existing CustomerProfile system into a comprehensive Customer Context Vault with:
- **Lineage tracking**: `source_item_id` for derivation chains
- **Explicit status management**: `active | superseded | expired | orphaned` lifecycle
- **Schema layer**: `ProfileFieldDefinition` + `ScenarioFieldRequirement`
- **ProfileItemSchemaExtraction**: LLM-based auto-extraction of required fields from scenarios/rules
- **Hatchet background jobs**: Scheduled expiry and orphan detection
- **Redis caching**: Two-tier storage matching SessionStore pattern

## Technical Context

**Language/Version**: Python 3.11+ (required for tomllib)
**Primary Dependencies**: FastAPI, Pydantic, structlog, redis, asyncpg, hatchet-sdk, SQLAlchemy
**Storage**: PostgreSQL 14+ (pgvector), Redis 6+ (caching)
**Testing**: pytest, pytest-asyncio, pytest-recording (for LLM calls), Docker Compose
**Target Platform**: Linux server (containerized)
**Project Type**: Single project (backend API)
**Performance Goals**: Profile load <10ms p99 (cached), <50ms p99 (DB), Schema validation <5ms, Extraction <5s
**Constraints**: Cache hit rate >80%, No data loss on Redis failure, Zero downtime migrations
**Scale/Scope**: Multi-tenant, 1000+ profiles per tenant, 10+ fields per profile

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Compliance | Notes |
|-----------|------------|-------|
| **API-first** | PASS | Profile management via REST API, no SDK-only features |
| **Zero In-Memory State** | PASS | All profile data in PostgreSQL, cached in Redis |
| **Multi-Tenant Native** | PASS | `tenant_id` on all tables, all queries filter by tenant |
| **Hot-Reload** | PASS | ProfileFieldDefinition changes take effect immediately |
| **Full Auditability** | PASS | Field status transitions logged, lineage tracked |
| **Four Stores** | N/A | ProfileStore is separate (5th store per existing design) |
| **Interface-First** | PASS | ProfileStore ABC, InMemoryProfileStore, PostgresProfileStore |
| **Provider Model** | PASS | LLMExecutor for extraction, EmbeddingProvider if needed |
| **Dependency Injection** | PASS | All stores/services injected via constructors |
| **Async Everywhere** | PASS | All ProfileStore methods are async |
| **Testing Standards** | PASS | Contract tests, 85% coverage target |

## Project Structure

### Documentation (this feature)

```text
specs/010-customer-context-vault/
├── plan.md              # This file
├── research.md          # Phase 0 output (Hatchet research)
├── data-model.md        # Phase 1 output (already created)
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (already created)
│   ├── data-model.md    # Enhanced models + PostgreSQL schema
│   └── store-interfaces.md  # ProfileStore interface
└── tasks.md             # Phase 2 output (already created)
```

### Source Code (repository root)

```text
focal/
├── profile/
│   ├── __init__.py
│   ├── models.py            # ProfileField, ProfileAsset, ProfileFieldDefinition, etc.
│   ├── enums.py             # ItemStatus, SourceType, RequiredLevel, FallbackAction
│   ├── store.py             # ProfileStore ABC
│   ├── validation.py        # SchemaValidationService
│   ├── extraction.py        # ProfileItemSchemaExtractor
│   └── stores/
│       ├── __init__.py
│       ├── inmemory.py      # InMemoryProfileStore
│       ├── postgres.py      # PostgresProfileStore
│       └── cached.py        # CachedProfileStore wrapper
├── jobs/
│   ├── __init__.py
│   ├── client.py            # Hatchet client wrapper
│   └── workflows/
│       ├── __init__.py
│       ├── profile_expiry.py
│       ├── orphan_detection.py
│       └── schema_extraction.py
├── db/migrations/versions/
│   ├── 006_profile_fields_enhancement.py
│   ├── 007_profile_assets_enhancement.py
│   ├── 008_profile_field_definitions.py
│   └── 009_scenario_field_requirements.py
└── alignment/migration/
    └── gap_fill.py          # Enhanced with schema integration

tests/
├── unit/
│   ├── profile/
│   │   ├── test_models.py
│   │   ├── test_validation.py
│   │   ├── test_extraction.py
│   │   └── stores/
│   │       ├── test_inmemory_profile.py
│   │       └── test_cached_profile.py
│   └── jobs/
│       └── test_workflows.py
├── contract/
│   └── test_profile_store_contract.py
├── integration/
│   ├── stores/
│   │   ├── test_postgres_profile.py
│   │   └── test_cached_profile.py
│   ├── jobs/
│   │   └── test_hatchet_workflows.py
│   └── alignment/
│       └── test_profile_requirements.py
└── performance/
    └── test_profile_performance.py
```

**Structure Decision**: Single backend project following existing Focal folder structure. ProfileStore is a domain-aligned store alongside ConfigStore, MemoryStore, SessionStore, and AuditStore.

---

## Design Principles

### 1. Extend, Don't Replace
All changes are **additive** to existing models. No breaking changes to current `ProfileStore` consumers.

### 2. Lineage is First-Class
Every piece of derived data tracks its source via `source_item_id`. This enables:
- Audit trail for compliance
- Cascade invalidation when source changes
- Explainability for AI-extracted data

### 3. Status Over Expiry
Replace implicit expiry checking (`expires_at < now()`) with explicit `status` field:
- Clearer query semantics
- Historical data preserved
- No accidental data loss

### 4. Schema Drives Collection
Field definitions tell the system:
- What to collect (validation rules)
- How to collect (prompts, extraction hints)
- What to protect (PII flags)

---

## Implementation Phases

### Phase 1: Model Enhancements

**Goal**: Add new fields to existing models, create new schema models.

```
ProfileField
├── + id: UUID (for lineage tracking)
├── + source_item_id: UUID | None
├── + source_item_type: SourceType
├── + source_metadata: dict
├── + status: ItemStatus (active | superseded | expired | orphaned)
├── + superseded_by_id: UUID | None
├── + field_definition_id: UUID | None
└── + is_orphaned: bool (computed property)

ProfileAsset
├── + source_item_id: UUID | None
├── + source_item_type: SourceType
├── + derived_from_tool: str | None
├── + status: ItemStatus
├── + analysis_field_ids: list[UUID]
└── + is_orphaned: bool (computed property)

NEW: ProfileFieldDefinition (schema)
NEW: ScenarioFieldRequirement (bindings)
NEW: ItemStatus enum (active | superseded | expired | orphaned)
NEW: SourceType enum
```

**Testing**: Unit tests for all model changes.

---

### Phase 2: Store Interface Updates

**Goal**: Extend `ProfileStore` interface with new methods.

**New Methods**:
```python
# Status-aware queries
get_field(profile_id, name, status=ACTIVE) -> ProfileField | None
get_field_history(profile_id, name) -> list[ProfileField]
expire_stale_fields(tenant_id) -> int
mark_orphaned_items(tenant_id) -> int

# Lineage
get_derivation_chain(item_id, item_type) -> list[dict]
get_derived_items(source_item_id) -> dict[str, list]
check_has_dependents(item_id) -> bool

# Schema
get_field_definitions(agent_id) -> list[ProfileFieldDefinition]
save_field_definition(definition) -> UUID
get_scenario_requirements(scenario_id) -> list[ScenarioFieldRequirement]
get_missing_fields(profile, scenario_id) -> list[ScenarioFieldRequirement]

# Soft-delete enforcement
delete_field(field_id) -> None  # Raises if has dependents
delete_asset(asset_id) -> None  # Raises if has dependents
```

**Implementation Order**:
1. Update `ProfileStore` ABC
2. Implement in `InMemoryProfileStore`
3. Create contract test suite (including soft-delete tests)
4. All tests pass before Phase 3

---

### Phase 3: Database Schema

**Goal**: Alembic migrations for all new tables/columns.

**Migrations**:
1. `006_profile_fields_enhancement.py` - Add lineage + status columns
2. `007_profile_assets_enhancement.py` - Add lineage + status columns
3. `008_profile_field_definitions.py` - New table
4. `009_scenario_field_requirements.py` - New table

**Key Indexes**:
- `profile_fields(source_item_id)` - Lineage queries
- `profile_fields(profile_id, name) WHERE status='active'` - Active field lookup
- `profile_field_definitions(tenant_id, agent_id)` - Schema lookup
- `scenario_field_requirements(scenario_id)` - Requirements lookup

**PostgresProfileStore Update**:
- Implement all new interface methods
- Use CTEs for efficient lineage traversal
- Handle superseding in transactions
- Enforce soft-delete in delete methods

---

### Phase 4: Redis Caching

**Goal**: Two-tier caching for ProfileStore.

**Architecture**:
```
┌─────────────────┐     miss      ┌─────────────────┐
│  CachedProfile  │ ───────────►  │  PostgresProfile │
│     Store       │ ◄───────────  │      Store       │
│   (wrapper)     │    reload     │   (backend)      │
└────────┬────────┘               └─────────────────┘
         │
    ┌────▼────┐
    │  Redis  │  TTL: 30 min
    └─────────┘
```

**Cache Keys**:
- `profile:{tenant}:{customer}` - Full profile
- `field_defs:{tenant}:{agent}` - Field definitions
- `scenario_reqs:{tenant}:{scenario}` - Requirements

**Invalidation Strategy**:
- Write-through: Update DB, then invalidate cache
- TTL-based expiry for eventual consistency
- Explicit invalidation on mutations

**Metrics**:
- Cache hit/miss rate collection for SC-004 validation

---

### Phase 5: Hatchet Background Jobs

**Goal**: Scheduled tasks for field expiry and orphan detection.

**Workflows**:
```python
@hatchet.workflow(cron="*/5 * * * *")  # Every 5 minutes
class ExpireStaleFieldsWorkflow:
    @hatchet.step()
    async def expire_fields(self, ctx) -> dict:
        # Mark fields past expires_at as status="expired"
        count = await profile_store.expire_stale_fields(tenant_id)
        return {"expired_count": count}

@hatchet.workflow(cron="*/15 * * * *")  # Every 15 minutes
class DetectOrphanedItemsWorkflow:
    @hatchet.step()
    async def detect_orphans(self, ctx) -> dict:
        # Mark items with deleted source as status="orphaned"
        count = await profile_store.mark_orphaned_items(tenant_id)
        return {"orphaned_count": count}
```

**Requirements**:
- All workflows are idempotent
- Graceful degradation if Hatchet unavailable
- Worker deployable independently from API pods

---

### Phase 6: ProfileItemSchemaExtraction

**Goal**: Automatic extraction of required profile fields from scenarios/rules.

**ProfileItemSchemaExtractor**:
```python
class ProfileItemSchemaExtractor:
    def __init__(self, llm_executor: LLMExecutor, config_store: ConfigStore):
        ...

    async def extract_requirements(
        self,
        scenario_or_rule: Scenario | Rule
    ) -> list[ScenarioFieldRequirement]:
        # Use LLM to analyze conditions and extract required fields
        ...

    async def suggest_field_definitions(
        self,
        field_names: list[str]
    ) -> list[ProfileFieldDefinition]:
        # Generate schema suggestions for undefined fields
        ...
```

**Integration**:
- Triggered on Scenario create/update via Hatchet workflow
- Triggered on Rule create/update via Hatchet workflow
- Non-blocking: failures don't block scenario/rule creation
- Confidence scoring: `needs_human_review=True` when < 0.8

---

### Phase 7: Integration

**Goal**: Connect all components, integration testing.

**GapFillService Enhancement**:
```
1. ScenarioFilter checks scenario requirements
2. get_missing_fields() returns unmet requirements
3. GapFillService attempts to fill each:
   a. Check CustomerProfile (existing)
   b. Check Session variables (existing)
   c. LLM extraction with collection_prompt (enhanced)
4. Track lineage for extracted values
5. Validate against schema before persistence
```

**New GapFillResult Fields**:
- `field_definition` - Schema for the field
- `validation_errors` - If extraction failed validation
- `source_item_id` / `source_item_type` - Lineage tracking

**Testing**:
- Full stack integration tests
- Redis failure recovery tests
- Hatchet unavailability tests

---

### Phase 8: Observability & Documentation

**Goal**: Metrics, logging, documentation, NFR validation.

**Metrics**:
- Cache hit/miss rates
- Derivation chain depth distribution
- Schema validation error rates
- Gap fill success rates by source
- Extraction success/failure rates

**Logging**:
- Field status transitions
- Cache operations
- Lineage traversal
- Validation failures
- Extraction results

**NFR Testing**:
- Performance test suite against NFR-001 through NFR-005
- Benchmark results exported to `benchmarks/`

---

## Phase Dependencies & Parallelization

| Phase | Dependencies | Parallelizable With |
|-------|--------------|---------------------|
| 1. Model Enhancements | None | - |
| 2. Store Interface | Phase 1 | - |
| 3. Database Schema | Phase 2, Project Phase 9 | - |
| 4. Redis Caching | Phase 3 | Phase 5 |
| 5. Hatchet Background Jobs | Phase 3 | Phase 4 |
| 6. ProfileItemSchemaExtraction | Phase 5 | - |
| 7. Integration | Phases 4, 5, 6, Project Phase 8 | - |
| 8. Observability & Documentation | Phase 7 | - |

**Critical Path**: 1 → 2 → 3 → (4 ∥ 5) → 6 → 7 → 8

**Notes**:
- Phases 4 and 5 can run in parallel after Phase 3 completes
- Project Phase 9 (PostgresProfileStore) must be complete before CCV Phase 3
- Project Phase 8 (GapFillService) must be complete before CCV Phase 7

---

## Risk Mitigation

### Risk 1: Breaking Existing Code
**Mitigation**: All new fields have defaults. Existing code continues to work.

### Risk 2: Performance Regression
**Mitigation**:
- Redis caching reduces DB load
- Indexed queries for common patterns
- Performance tests validate NFRs

### Risk 3: Complex Migrations
**Mitigation**:
- Incremental migrations (one per concern)
- All migrations have downgrade functions
- Test on staging before production

### Risk 4: Redis Failures
**Mitigation**:
- CachedProfileStore falls back to backend on Redis errors
- No data loss possible (cache is read-through)

### Risk 5: Hatchet Unavailability
**Mitigation**:
- API continues serving without blocking
- Jobs queued locally and retried
- Manual expiry endpoint as fallback

---

## Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| PostgresProfileStore | In Progress (Project Phase 9) | Base implementation needed before CCV Phase 3 |
| Redis | Available | Used by SessionStore |
| Alembic | Available | Used for migrations |
| Hatchet | New | For background job orchestration |
| LLMExecutor | Available | For ProfileItemSchemaExtraction |
| GapFillService | Complete (Project Phase 8) | Needs enhancement in CCV Phase 7 |

---

## Success Criteria

1. **Lineage Works**: Can trace any derived field back to its source
2. **Status Works**: Old values preserved, queries return only active
3. **Schema Works**: Invalid fields rejected (or warned)
4. **Cache Works**: >80% hit rate, <10ms p99 latency
5. **Gap Fill Works**: Uses schema prompts, tracks lineage
6. **Tests Pass**: 100% contract tests, 85%+ coverage
7. **Migrations Work**: Apply and rollback cleanly

---

## Files to Create/Modify

### New Files
```
# Models & Enums
focal/profile/enums.py (additions: ItemStatus, SourceType)

# Services
focal/profile/validation.py
focal/profile/extraction.py (ProfileItemSchemaExtractor)

# Stores
focal/profile/stores/cached.py

# Background Jobs (Hatchet)
focal/jobs/__init__.py
focal/jobs/client.py (Hatchet client wrapper)
focal/jobs/workflows/__init__.py
focal/jobs/workflows/profile_expiry.py
focal/jobs/workflows/orphan_detection.py
focal/jobs/workflows/schema_extraction.py

# Database Migrations
focal/db/migrations/versions/006_profile_fields_enhancement.py
focal/db/migrations/versions/007_profile_assets_enhancement.py
focal/db/migrations/versions/008_profile_field_definitions.py
focal/db/migrations/versions/009_scenario_field_requirements.py

# Tests
tests/unit/profile/test_validation.py
tests/unit/profile/test_extraction.py
tests/unit/profile/stores/test_cached_profile.py
tests/unit/jobs/test_workflows.py
tests/contract/test_profile_store_contract.py
tests/integration/stores/test_cached_profile.py
tests/integration/alignment/test_profile_requirements.py
tests/integration/jobs/test_hatchet_workflows.py
tests/performance/test_profile_performance.py
```

### Modified Files
```
focal/profile/models.py
focal/profile/store.py
focal/profile/stores/inmemory.py
focal/profile/stores/postgres.py
focal/profile/__init__.py
focal/alignment/migration/gap_fill.py
focal/alignment/engine.py
focal/config/models/storage.py
focal/config/models/jobs.py (new Hatchet config)
focal/observability/metrics.py
config/default.toml
docs/design/customer-profile.md
IMPLEMENTATION_PLAN.md
pyproject.toml (add hatchet-sdk dependency)
docker-compose.yml (add Hatchet services)
```

---

## See Also

- `contracts/data-model.md` - Enhanced models and PostgreSQL schema
- `contracts/store-interfaces.md` - ProfileStore interface specification
- `tasks.md` - Detailed implementation checklist
- `docs/design/customer-profile.md` - Original design document
- `specs/008-scenario-migration/spec.md` - GapFillService integration
- `specs/009-production-stores-providers/spec.md` - PostgresProfileStore base
