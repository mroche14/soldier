# Implementation Plan: Scenario Migration System

**Branch**: `008-scenario-migration` | **Date**: 2025-11-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/008-scenario-migration/spec.md`

## Summary

Implement an anchor-based scenario migration system that enables safe scenario updates while customers have active sessions. The system uses content hashing for semantic node matching across versions, two-phase deployment (mark at deploy, apply at JIT), per-anchor policies for granular control, and three migration scenarios (Clean Graft, Gap Fill, Re-Routing) with checkpoint blocking to prevent undoing irreversible actions.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI, pydantic, pydantic-settings, structlog (existing); hashlib (stdlib for content hashing)
**Storage**: ConfigStore (migration plans, archived versions), SessionStore (pending_migration flag, step_history), ProfileStore (gap fill)
**Testing**: pytest with InMemory store implementations, pytest-recording for LLM extraction tests
**Target Platform**: Linux server (containerized)
**Project Type**: Single Python package (soldier/)
**Performance Goals**: Migration plan generation < 5s for 50-step scenarios; JIT reconciliation < 100ms
**Constraints**: Zero in-memory state, multi-tenant isolation, async everywhere
**Scale/Scope**: Support scenarios with up to 100 steps, 10k+ concurrent sessions per tenant

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| API-first | ✅ PASS | Migration plans created/approved via API, reconciliation triggered via turn API |
| Zero In-Memory State | ✅ PASS | Migration plans stored in ConfigStore, pending flags in SessionStore |
| Multi-Tenant Native | ✅ PASS | All entities scoped by tenant_id, queries filtered |
| Hot-Reload | ✅ PASS | Migration plans take effect immediately after approval |
| Full Auditability | ✅ PASS | All migration applications logged to AuditStore |
| Interface-First Design | ✅ PASS | Migration services use existing Store interfaces |
| Dependency Injection | ✅ PASS | Services receive stores via __init__ |
| Async Everywhere | ✅ PASS | All I/O operations async |
| Four Stores | ✅ PASS | ConfigStore (plans), SessionStore (pending_migration), AuditStore (logs) |

## Project Structure

### Documentation (this feature)

```text
specs/008-scenario-migration/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
soldier/
├── alignment/
│   ├── migration/           # NEW: Migration system
│   │   ├── __init__.py
│   │   ├── models.py        # MigrationPlan, TransformationMap, etc.
│   │   ├── diff.py          # Graph diff, content hashing, anchor detection
│   │   ├── planner.py       # Migration plan generation
│   │   ├── executor.py      # JIT migration execution (reconciliation)
│   │   ├── gap_fill.py      # Gap fill logic (profile/session/extraction)
│   │   └── composite.py     # Multi-version composite migration
│   └── stores/
│       └── config_store.py  # EXTEND: add migration plan methods
├── conversation/
│   └── stores/
│       └── session_store.py # EXTEND: add pending_migration, step_history
├── api/
│   └── routes/
│       └── migrations.py    # NEW: Migration API endpoints
└── config/
    └── models/
        └── migration.py     # NEW: Migration configuration models

tests/
├── unit/
│   └── alignment/
│       └── migration/       # NEW: Unit tests
│           ├── test_diff.py
│           ├── test_planner.py
│           ├── test_executor.py
│           ├── test_gap_fill.py
│           └── test_composite.py
└── integration/
    └── alignment/
        └── migration/       # NEW: Integration tests
            └── test_migration_flow.py
```

**Structure Decision**: New `soldier/alignment/migration/` module follows existing pattern of domain-aligned folders. Migration is part of the alignment pipeline (pre-turn reconciliation) so it belongs under alignment/.

## Complexity Tracking

> No constitution violations requiring justification.

| Aspect | Complexity | Justification |
|--------|------------|---------------|
| Content Hashing | Low | stdlib hashlib, simple JSON serialization |
| Graph Traversal | Medium | BFS/DFS for upstream/downstream analysis, visited sets for cycles |
| Gap Fill Extraction | Medium | Reuses existing LLMProvider, structured output |
| Composite Migration | Medium | In-memory simulation, requirement pruning |
